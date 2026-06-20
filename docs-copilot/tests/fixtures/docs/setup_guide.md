# Setup Guide

This guide walks through installing and configuring the application for local development.

## Installation

Clone the repository and install dependencies with `pip install -r requirements.txt`. Python 3.10 or newer is required. We recommend creating a virtual environment before installing packages so that dependencies stay isolated from other projects on your machine.

## Database Configuration

To configure the database, set `DATABASE_URL` in your `.env` file. The application supports PostgreSQL and SQLite out of the box. For local development, SQLite is the simplest option:

```
DATABASE_URL=sqlite:///local.db
```

For production, point `DATABASE_URL` at your PostgreSQL instance. Run `python manage.py migrate` after changing the connection string to apply schema migrations.

## Account Settings

You can reset your password from the Settings page. Navigate to your profile, click "Account Settings", and select "Reset Password". A confirmation email will be sent to the address on file. Password resets expire after 24 hours if not completed.
