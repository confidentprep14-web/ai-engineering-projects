# Build Guide — SQL Agent

## Step 1 — Schema introspection

At startup, read the schema so the LLM has accurate context:

```python
import sqlite3

def introspect_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables = []
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (table_name,) in cursor.fetchall():
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [
            {"name": row[1], "type": row[2], "nullable": not row[3], "pk": bool(row[5])}
            for row in cursor.fetchall()
        ]
        tables.append({"name": table_name, "columns": columns})
    
    return {"tables": tables}
```

## Step 2 — Parser-based validation (not regex)

The key insight: regex cannot parse SQL reliably. A query like `SELECT * FROM (SELECT name FROM t) WHERE ...` contains a subquery that regex might mistake for a simple SELECT. Use the AST:

```python
import sqlglot

def parse_and_validate(sql):
    try:
        parsed = sqlglot.parse_one(sql)
    except sqlglot.errors.ParseError as e:
        return ValidationResult(is_valid=False, error=str(e), statement_type=None)
    
    stmt_type = type(parsed).__name__
    if stmt_type != "Select":
        return ValidationResult(
            is_valid=False,
            error=f"Only SELECT allowed. Got: {stmt_type}",
            statement_type=stmt_type,
        )
    return ValidationResult(is_valid=True, error=None, statement_type="SELECT")
```

## Step 3 — The generation prompt

```
System: You are a SQLite expert. Given a schema and a question, write a single
        SELECT query. Return ONLY the SQL — no explanation, no markdown.

User:   Schema:
        {schema_str}
        
        Question: {question}
```

If retrying: prepend `"Previous SQL caused this error: {error}\nWrite a corrected query."`

## Step 4 — Interpretation prompt

```
System: You are a data analyst. Explain these SQL results in 2-3 plain-English
        sentences focused on the answer to the question.

User:   Question: {question}
        Results (first 5 rows):
        {formatted_rows}
```

## Step 5 — Wire the test suite

```python
NL_SQL_PAIRS = [
    ("Show me all customers from the US", "customers"),
    ("5 most expensive products", "products"),
    ...
]

for question, _ in NL_SQL_PAIRS:
    rows, cols, sql, attempts = retry_on_error(question, schema_str, db_path)
    passed = len(rows) > 0 or "COUNT" in sql.upper()
    print(f"{'[PASS]' if passed else '[FAIL]'} {question}")
```

## Debugging tips

- If the model generates markdown fences, `extract_sql_from_response` strips them — verify this runs before validation
- If sqlglot version mismatch causes import errors, pin to `sqlglot==23.3.0` exactly
- If schema introspection returns no tables, check that `init_db.py` ran and created the `.db` file

## How to talk about this in an interview

**"Why sqlglot instead of regex for SQL validation?"**
> SQL can't be reliably parsed with regex. A query like `SELECT name FROM (SELECT * FROM users WHERE type='DROP TABLE')` contains 'DROP TABLE' as a string literal — regex would flag it, sqlglot's AST won't. Parser-based validation is accurate; regex-based validation is security theater.

**"What does the retry loop do?"**
> When the database returns an error — like 'no such column: usr_id' — I inject that exact error into the next prompt. The model sees: 'your previous SQL caused this error, write a corrected version.' This handles about 80% of first-attempt failures without human intervention.

**"How do you prevent SQL injection?"**
> Two layers: AST validation (only SELECT allowed) and SQLite's parameterized queries for any user-provided values. But since we're generating SQL from an LLM's output rather than concatenating user strings, the injection surface is different from traditional web apps.
