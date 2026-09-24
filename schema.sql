-- CityBike Hub – relational schema (SQLite)
-- Running this file resets the database: tables are dropped and recreated.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS OrderItem;
DROP TABLE IF EXISTS RentalOrder;
DROP TABLE IF EXISTS Item;
DROP TABLE IF EXISTS Category;
DROP TABLE IF EXISTS Customer;

CREATE TABLE Customer (
    customer_id INTEGER PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    phone       TEXT NOT NULL
);

CREATE TABLE Category (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE Item (
    item_id        INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL,
    category_id    INTEGER NOT NULL,
    total_quantity INTEGER NOT NULL CHECK (total_quantity >= 0),
    price_per_day  INTEGER NOT NULL CHECK (price_per_day >= 0),   -- NOK
    FOREIGN KEY (category_id) REFERENCES Category(category_id)
);

CREATE TABLE RentalOrder (
    order_id    INTEGER PRIMARY KEY,
    start_date  TEXT    NOT NULL,                     -- ISO format YYYY-MM-DD
    end_date    TEXT,                                 -- NULL while the order is active
    status      TEXT    NOT NULL CHECK (status IN ('active', 'closed')),
    customer_id INTEGER NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id),
    CHECK (end_date IS NULL OR end_date >= start_date)
);

-- Associative table: resolves the many-to-many relationship between orders and items
CREATE TABLE OrderItem (
    order_id    INTEGER NOT NULL,
    item_id     INTEGER NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    return_date TEXT,                                 -- NULL while the item is still on loan
    lost        INTEGER NOT NULL DEFAULT 0 CHECK (lost IN (0, 1)),
    PRIMARY KEY (order_id, item_id),
    FOREIGN KEY (order_id) REFERENCES RentalOrder(order_id),
    FOREIGN KEY (item_id)  REFERENCES Item(item_id)
);
