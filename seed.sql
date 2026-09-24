-- Sample data for CityBike Hub (fictional customers)

INSERT INTO Customer (customer_id, first_name, last_name, email, phone) VALUES
(1, 'Ola',   'Nordmann', 'ola.nordmann@example.com',  '11111111'),
(2, 'Kari',  'Hansen',   'kari.hansen@example.com',   '22222222'),
(3, 'Per',   'Olsen',    'per.olsen@example.com',     '33333333'),
(4, 'Ingrid','Berg',     'ingrid.berg@example.com',   '44444444');

INSERT INTO Category (category_id, name) VALUES
(1, 'vehicle'),
(2, 'safety equipment'),
(3, 'accessories');

INSERT INTO Item (item_id, name, category_id, total_quantity, price_per_day) VALUES
(1, 'City Bike 16"',     1,  5, 100),
(2, 'Electric Scooter',  1,  3, 150),
(3, 'Helmet M',          2, 10,  30),
(4, 'Reflective Vest',   2,  8,  15),
(5, 'Bike Lock',         3,  6,  20),
(6, 'Child Seat',        3,  2,  40);

-- Closed orders (history used in the revenue analysis)
INSERT INTO RentalOrder (order_id, start_date, end_date, status, customer_id) VALUES
(1, '2025-11-10', '2025-11-11', 'closed', 1),
(2, '2025-11-12', '2025-11-15', 'closed', 2),
(3, '2025-11-14', '2025-11-14', 'closed', 3),
(4, '2025-11-15', '2025-11-20', 'closed', 4),
(5, '2025-11-18', '2025-11-19', 'closed', 1);

INSERT INTO OrderItem (order_id, item_id, quantity, return_date, lost) VALUES
(1, 1, 1, '2025-11-11', 0),
(1, 3, 1, '2025-11-11', 0),
(2, 2, 2, '2025-11-15', 0),
(2, 3, 2, '2025-11-15', 0),
(3, 1, 1, '2025-11-14', 0),
(3, 5, 1, '2025-11-14', 1),   -- lock reported lost
(4, 1, 2, '2025-11-20', 0),
(4, 6, 1, '2025-11-20', 0),
(4, 4, 2, '2025-11-20', 0),
(5, 2, 1, '2025-11-19', 0);
