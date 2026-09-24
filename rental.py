"""
CityBike Hub – rental system on top of a SQLite database.

The business logic (functions that take a connection) is kept separate from the
command-line interface at the bottom of the file, so it can be tested
without typing input by hand.

Usage:
    python rental.py --reset      # create the database from schema.sql + seed.sql
    python rental.py              # start the interactive rental program
"""

import argparse
import sqlite3
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "citybike.db"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def get_connection(db_path=DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign-key enforcement switched on.

    SQLite ignores FOREIGN KEY constraints unless this PRAGMA is set
    on every new connection.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection, with_seed: bool = True) -> None:
    """(Re)create all tables and optionally load the sample data."""
    conn.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    if with_seed:
        conn.executescript((BASE_DIR / "seed.sql").read_text(encoding="utf-8"))
    conn.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def rental_days(start: str, end: str) -> int:
    """Number of days billed. Same-day rentals count as one day."""
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return max(1, days)


def get_customer(conn, customer_id: int):
    return conn.execute(
        "SELECT first_name, last_name FROM Customer WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()


def get_active_order_id(conn, customer_id: int):
    """Return the customer's active order_id, or None."""
    row = conn.execute(
        "SELECT order_id FROM RentalOrder WHERE customer_id = ? AND status = 'active'",
        (customer_id,),
    ).fetchone()
    return row[0] if row else None


def get_available_quantity(conn, item_id: int) -> int:
    """Units in stock = total - units currently on loan - units reported lost."""
    row = conn.execute(
        """
        SELECT i.total_quantity
               - COALESCE(SUM(CASE WHEN oi.return_date IS NULL THEN oi.quantity END), 0)
               - COALESCE(SUM(CASE WHEN oi.lost = 1          THEN oi.quantity END), 0)
        FROM Item i
        LEFT JOIN OrderItem oi ON oi.item_id = i.item_id
        WHERE i.item_id = ?
        GROUP BY i.item_id
        """,
        (item_id,),
    ).fetchone()
    return row[0] if row else 0


def list_items(conn):
    """All items with category, current availability and daily price."""
    rows = conn.execute(
        """
        SELECT i.item_id, i.name, c.name, i.price_per_day
        FROM Item i
        JOIN Category c ON c.category_id = i.category_id
        ORDER BY i.item_id
        """
    ).fetchall()
    return [
        (item_id, name, category, get_available_quantity(conn, item_id), price)
        for item_id, name, category, price in rows
    ]


# ---------------------------------------------------------------------------
# Rental workflow
# ---------------------------------------------------------------------------

class RentalError(Exception):
    """Raised when a rental action is not allowed."""


def create_order(conn, customer_id: int, today: str | None = None) -> int:
    """Create a new active order and return its id (assigned by SQLite)."""
    today = today or date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO RentalOrder (start_date, end_date, status, customer_id) "
        "VALUES (?, NULL, 'active', ?)",
        (today, customer_id),
    )
    conn.commit()
    return cur.lastrowid


def borrow_item(conn, customer_id: int, item_id: int, quantity: int,
                today: str | None = None) -> int:
    """Add `quantity` units of an item to the customer's active order.

    Creates an order if the customer has none. Returns the order_id.
    """
    if get_customer(conn, customer_id) is None:
        raise RentalError(f"Customer {customer_id} does not exist.")
    if quantity <= 0:
        raise RentalError("Quantity must be positive.")

    available = get_available_quantity(conn, item_id)
    if quantity > available:
        raise RentalError(f"Not enough units available (only {available} left).")

    order_id = get_active_order_id(conn, customer_id) or create_order(conn, customer_id, today)

    existing = conn.execute(
        "SELECT return_date FROM OrderItem WHERE order_id = ? AND item_id = ?",
        (order_id, item_id),
    ).fetchone()

    if existing is None:
        conn.execute(
            "INSERT INTO OrderItem (order_id, item_id, quantity) VALUES (?, ?, ?)",
            (order_id, item_id, quantity),
        )
    elif existing[0] is None:
        # Item is already on loan in this order – add to the quantity
        conn.execute(
            "UPDATE OrderItem SET quantity = quantity + ? WHERE order_id = ? AND item_id = ?",
            (quantity, order_id, item_id),
        )
    else:
        # (order_id, item_id) is the primary key, so an item that has been
        # returned cannot be borrowed again in the same order.
        raise RentalError("This item was already returned in the current order.")

    conn.commit()
    return order_id


def return_item(conn, customer_id: int, item_id: int, lost: bool = False,
                today: str | None = None) -> bool:
    """Register the return (or loss) of an item.

    Returns True if this closed the order (all items returned).
    """
    today = today or date.today().isoformat()
    order_id = get_active_order_id(conn, customer_id)
    if order_id is None:
        raise RentalError("This customer has no active rental order.")

    cur = conn.execute(
        "UPDATE OrderItem SET return_date = ?, lost = ? "
        "WHERE order_id = ? AND item_id = ? AND return_date IS NULL",
        (today, int(lost), order_id, item_id),
    )
    if cur.rowcount == 0:
        raise RentalError(f"Item {item_id} is not on loan in order {order_id}.")

    remaining = conn.execute(
        "SELECT COUNT(*) FROM OrderItem WHERE order_id = ? AND return_date IS NULL",
        (order_id,),
    ).fetchone()[0]

    if remaining == 0:
        conn.execute(
            "UPDATE RentalOrder SET status = 'closed', end_date = ? WHERE order_id = ?",
            (today, order_id),
        )
    conn.commit()
    return remaining == 0


def build_receipt(conn, order_id: int) -> str:
    """Return a formatted receipt for a closed order."""
    row = conn.execute(
        """
        SELECT c.first_name, c.last_name, ro.start_date, ro.end_date
        FROM RentalOrder ro
        JOIN Customer c ON c.customer_id = ro.customer_id
        WHERE ro.order_id = ?
        """,
        (order_id,),
    ).fetchone()
    if row is None:
        raise RentalError(f"Order {order_id} not found.")

    first, last, start, end = row
    days = rental_days(start, end)
    items = conn.execute(
        """
        SELECT i.name, oi.quantity, i.price_per_day, oi.lost
        FROM OrderItem oi
        JOIN Item i ON i.item_id = oi.item_id
        WHERE oi.order_id = ?
        """,
        (order_id,),
    ).fetchall()

    lines = [
        "===== RENTAL RECEIPT =====",
        f"Customer: {first} {last}",
        f"Order ID: {order_id}",
        f"Period:   {start} to {end} ({days} day{'s' if days != 1 else ''})",
        "",
    ]
    total = 0
    for name, qty, price, lost in items:
        subtotal = qty * price * days
        total += subtotal
        flag = "  [REPORTED LOST]" if lost else ""
        lines.append(f"- {name}: {qty} × {price} NOK × {days} days = {subtotal} NOK{flag}")
    lines += ["", f"TOTAL: {total} NOK", "=========================="]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def ask_int(prompt: str):
    try:
        return int(input(prompt))
    except ValueError:
        print("Please enter a whole number.")
        return None


def run_cli(conn) -> None:
    customer_id = ask_int("Enter customer ID: ")
    if customer_id is None:
        return
    customer = get_customer(conn, customer_id)
    if customer is None:
        print(f"Customer {customer_id} does not exist.")
        return

    print(f"Welcome, {customer[0]} {customer[1]}!")
    order_id = get_active_order_id(conn, customer_id)
    print(f"Active order: {order_id}" if order_id else "No active rental order.")

    while True:
        choice = input("\n1 - Borrow  2 - Return  3 - Exit\nChoice: ").strip()
        try:
            if choice == "1":
                print("\nItems:")
                for item_id, name, category, available, price in list_items(conn):
                    print(f"  {item_id}: {name} ({category}) – {available} available – {price} NOK/day")
                item_id = ask_int("Item ID: ")
                qty = ask_int("Quantity: ")
                if item_id is None or qty is None:
                    continue
                order_id = borrow_item(conn, customer_id, item_id, qty)
                print(f"Borrowed {qty} × item {item_id} (order {order_id}).")

            elif choice == "2":
                item_id = ask_int("Item ID to return: ")
                if item_id is None:
                    continue
                lost = input("Was the item lost? (y/n): ").strip().lower() == "y"
                order_id = get_active_order_id(conn, customer_id)
                if return_item(conn, customer_id, item_id, lost):
                    print("All items returned – order closed.\n")
                    print(build_receipt(conn, order_id))
                else:
                    print(f"Item {item_id} registered as {'lost' if lost else 'returned'}.")

            elif choice == "3":
                print("Goodbye!")
                break
            else:
                print("Please choose 1, 2 or 3.")
        except RentalError as err:
            print(f"Error: {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CityBike Hub rental system")
    parser.add_argument("--reset", action="store_true",
                        help="recreate the database with sample data")
    args = parser.parse_args()

    connection = get_connection()
    if args.reset or not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        init_db(connection)
        print("Database created with sample data.")
    if not args.reset:
        try:
            run_cli(connection)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
    connection.close()
