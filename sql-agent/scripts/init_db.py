"""Creates ecommerce.db with the schema and sample data used by the SQL agent.

Schema: customers, products, orders (see README.md for the full DDL).
Sample data: 5 customers (US/UK/CA), 8 products (electronics/books/clothing),
15 orders spanning all four statuses.

Run: python scripts/init_db.py [--db <path>]
"""

import argparse
import os
import sqlite3

SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL,
    ordered_at TEXT NOT NULL
);
"""

CUSTOMERS = [
    (1, "Alice Johnson", "alice@example.com", "US", "2023-01-15T10:00:00"),
    (2, "Bob Smith", "bob@example.com", "UK", "2023-02-20T11:30:00"),
    (3, "Carla Diaz", "carla@example.com", "US", "2023-03-05T09:15:00"),
    (4, "David Chen", "david@example.com", "CA", "2023-04-10T14:45:00"),
    (5, "Emma Wilson", "emma@example.com", "UK", "2023-05-22T16:20:00"),
]

PRODUCTS = [
    (1, "Wireless Mouse", "electronics", 24.99, 50),
    (2, "Mechanical Keyboard", "electronics", 89.99, 30),
    (3, "USB-C Hub", "electronics", 39.99, 5),
    (4, "Noise Cancelling Headphones", "electronics", 199.99, 8),
    (5, "4K Monitor", "electronics", 299.99, 3),
    (6, "The Pragmatic Programmer", "books", 39.99, 25),
    (7, "Clean Code", "books", 9.99, 40),
    (8, "Cotton T-Shirt", "clothing", 14.99, 100),
]

ORDERS = [
    (1, 1, 1, 1, 24.99, "delivered", "2023-06-01T10:00:00"),
    (2, 1, 2, 1, 89.99, "delivered", "2023-06-02T11:00:00"),
    (3, 2, 3, 2, 79.98, "shipped", "2023-06-03T12:00:00"),
    (4, 2, 4, 1, 199.99, "pending", "2023-06-04T13:00:00"),
    (5, 3, 5, 1, 299.99, "delivered", "2023-06-05T14:00:00"),
    (6, 3, 6, 1, 39.99, "cancelled", "2023-06-06T15:00:00"),
    (7, 4, 7, 3, 29.97, "delivered", "2023-06-07T16:00:00"),
    (8, 4, 1, 2, 49.98, "shipped", "2023-06-08T17:00:00"),
    (9, 5, 2, 1, 89.99, "delivered", "2023-06-09T18:00:00"),
    (10, 1, 8, 4, 59.96, "delivered", "2023-06-10T19:00:00"),
    (11, 2, 6, 1, 39.99, "shipped", "2023-06-11T20:00:00"),
    (12, 3, 7, 2, 19.98, "pending", "2023-06-12T21:00:00"),
    (13, 1, 4, 1, 199.99, "delivered", "2023-06-13T22:00:00"),
    (14, 4, 5, 1, 299.99, "cancelled", "2023-06-14T23:00:00"),
    (15, 3, 1, 1, 24.99, "delivered", "2023-06-15T08:00:00"),
]


def init_db(db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.executescript(SCHEMA)
        cursor.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)", CUSTOMERS
        )
        cursor.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?)", PRODUCTS
        )
        cursor.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", ORDERS
        )
        conn.commit()
    finally:
        conn.close()

    print(f"Created {db_path}: {len(CUSTOMERS)} customers, {len(PRODUCTS)} products, {len(ORDERS)} orders")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the sample e-commerce SQLite database")
    parser.add_argument("--db", default=os.environ.get("DEFAULT_DB_PATH", "ecommerce.db"))
    args = parser.parse_args()
    init_db(args.db)


if __name__ == "__main__":
    main()
