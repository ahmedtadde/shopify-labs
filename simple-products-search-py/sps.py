import click
import duckdb
import os
import json
import glob
from tabulate import tabulate
from pathlib import Path
import re
from urllib.parse import urlparse


SPS_HOME = Path.home() / ".sps"
DEFAULT_DATASTORE = SPS_HOME / "datastore.duckdb"


def get_datastore_path(datastore):
    if datastore:
        return datastore
    if os.environ.get("DATASTORE"):
        datastore = os.environ.get("DATASTORE")
        if not datastore.startswith("/"):
            datastore = str(SPS_HOME / datastore)
        # ensure that the datastore path exists
        os.makedirs(datastore, exist_ok=True)
        return datastore
    datastore = DEFAULT_DATASTORE.parent.mkdir(parents=True, exist_ok=True)
    return str(DEFAULT_DATASTORE)


def connect_db(datastore):
    db_path = get_datastore_path(datastore)
    db = duckdb.connect(db_path)
    db.execute(
        "CREATE TABLE IF NOT EXISTS shop (slug VARCHAR PRIMARY KEY, hostname VARCHAR UNIQUE, name VARCHAR)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_shop_hostname ON shop (hostname)")
    return db


@click.group(name="sps")
@click.option("--datastore", default=None, help="Path to DuckDB datastore file")
@click.pass_context
def cli(ctx, datastore):
    """Simple Products Search CLI"""
    ctx.ensure_object(dict)
    ctx.obj["db"] = connect_db(datastore)


@cli.group()
def shop():
    """Manage shops"""
    pass


@shop.command("ls")
@click.pass_context
def list_shops(ctx):
    """List all shops"""
    shops = ctx.obj["db"].execute("SELECT * FROM shop").fetchall()
    if shops:
        headers = ["Slug", "Hostname", "Name"]
        click.echo(tabulate(shops, headers=headers, tablefmt="grid"))
    else:
        click.echo("No shops found.")


@shop.command("create")
@click.argument("identifier")
@click.option("--slug", help="Custom slug for the shop")
@click.option("--name", help="Name of the shop")
@click.pass_context
def create_shop(ctx, identifier, slug, name):
    """Create a new shop"""
    if not identifier:
        raise click.UsageError("URL or hostname is required for shop creation.")

    # Validate and normalize URL
    if not is_valid_url(identifier):
        raise click.UsageError(
            "Invalid URL or hostname. Please provide a valid domain."
        )

    # Extract and clean the hostname
    parsed_url = urlparse(
        identifier
        if identifier.startswith(("http://", "https://"))
        else "http://" + identifier
    )
    hostname = parsed_url.netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]  # Remove 'www.' if present

    # Extract slug if not provided
    if not slug:
        slug = normalize_into_slug(extract_slug_from_url(hostname))
    elif not slug.strip():
        raise click.UsageError("Slug must not be empty.")
    elif slug.strip() != normalize_into_slug(slug):
        raise click.UsageError(
            "Slug must be lowercase and contain only alphanumeric characters and hyphens."
        )
    slug = slug.strip()
    # check that slug is less than 128 characters but more than 2 alphanumeric characters
    if len(slug) < 2 or len(slug) > 128:
        raise click.UsageError("Slug must be between 2 and 128 characters.")

    # Check for uniqueness
    if check_shop_creation_conflict(ctx.obj["db"], slug, hostname):
        raise click.UsageError("A shop with this slug or hostname already exists.")

    ctx.obj["db"].execute(
        f"INSERT INTO shop (slug, hostname, name) VALUES (?, ?, ?)",
        (slug, hostname, name or ""),
    )
    click.echo(f"Shop with hostname '{hostname}' has been created with slug '{slug}'.")


@shop.command("get")
@click.argument("slug")
@click.pass_context
def get_shop(ctx, slug):
    """Get details of a specific shop"""
    shop = (
        ctx.obj["db"].execute(f"SELECT * FROM shop WHERE slug = ?", (slug,)).fetchone()
    )
    if shop:
        headers = ["Slug", "Hostname", "Name"]
        click.echo(tabulate([shop], headers=headers, tablefmt="grid"))
    else:
        click.echo(f"No shop found with slug '{slug}'.")


@shop.command("delete")
@click.argument("slug")
@click.pass_context
def delete_shop(ctx, slug):
    """Delete a shop"""
    result = ctx.obj["db"].execute(f"DELETE FROM shop WHERE slug = ?", (slug,))
    if result.rowcount > 0:
        click.echo(f"Shop with slug '{slug}' has been deleted.")
    else:
        click.echo(f"No shop found with slug '{slug}'.")


@shop.command("import")
@click.argument("file", type=click.Path(exists=True))
@click.option("--rebuild", is_flag=True, help="Rebuild the shop table")
@click.pass_context
def import_shops(ctx, file, rebuild):
    """Import shops from a CSV or JSON file"""
    import_shops_helper(ctx.obj["db"], file, rebuild)


def import_shops_helper(db, file_pattern, rebuild):
    if rebuild:
        db.execute("DROP TABLE IF EXISTS shop")
        db.execute("CREATE TABLE shop (slug VARCHAR, hostname VARCHAR, name VARCHAR)")

    files = glob.glob(file_pattern)
    for file in files:
        if file.endswith(".csv"):
            db.execute(
                f"""
                INSERT OR REPLACE INTO shop
                SELECT * FROM read_csv_auto('{file}')
            """
            )
        elif file.endswith(".json"):
            with open(file, "r") as f:
                data = json.load(f)
            db.execute(
                """
                INSERT OR REPLACE INTO shop
                SELECT * FROM json_to_df($1)
            """,
                [json.dumps(data)],
            )
        else:
            click.echo(f"Skipping unsupported file: {file}")

    click.echo(f"Imported data from {len(files)} file(s)")


def is_valid_url(url):
    if not url.startswith(("http://", "https://")):
        url = "http://" + url  # Assume http if no scheme is provided
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def extract_slug_from_url(url):
    parts = url.split(".")
    if len(parts) > 2:
        return parts[-2]  # Return the second-to-last part
    elif len(parts) == 2:
        return parts[0]  # Return the first part if there are only two
    else:
        return url  # Return the whole thing if it's just one part


def normalize_into_slug(slug):
    """
    Normalize a string into a slug (lowercase, alphanumeric, kebab-case)
    """
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    return slug


def check_shop_creation_conflict(db, slug, hostname):
    result = db.execute(
        "SELECT COUNT(*) FROM shop WHERE slug = ? OR hostname = ?", (slug, hostname)
    ).fetchone()[0]
    return result > 0


if __name__ == "__main__":
    cli()
