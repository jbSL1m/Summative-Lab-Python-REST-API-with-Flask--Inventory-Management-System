import argparse
import json
import sys

import requests


# The CLI sends requests to the local Flask development server by default.
DEFAULT_API_URL = "http://127.0.0.1:5000"


def request_api(method, path, api_url, **kwargs):
    # **kwargs passes optional values such as json= or params= to Requests.
    try:
        response = requests.request(method, f"{api_url.rstrip('/')}{path}", timeout=10, **kwargs)
    except requests.RequestException as error:
        print(f"Could not connect to the inventory API: {error}", file=sys.stderr)
        return 1

    # A successful DELETE uses status 204 and has no JSON response body.
    if response.status_code == 204:
        print("Inventory item deleted.")
        return 0

    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text or "The API returned an invalid response"}

    # Successful output goes to stdout; error output goes to stderr.
    output = sys.stdout if response.ok else sys.stderr
    print(json.dumps(body, indent=2), file=output)
    return 0 if response.ok else 1


def build_parser():
    # argparse reads terminal arguments and creates the help menu automatically.
    parser = argparse.ArgumentParser(description="Manage the e-commerce inventory API")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Inventory API base URL")
    # Subparsers create separate commands such as list, add, and delete.
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="List all inventory items")

    get_parser = commands.add_parser("get", help="Show one inventory item")
    get_parser.add_argument("id", type=int)

    add_parser = commands.add_parser("add", help="Add an inventory item")
    add_parser.add_argument("name")
    add_parser.add_argument("--price", type=float, default=0.0)
    add_parser.add_argument("--stock", type=int, default=0)
    add_parser.add_argument("--brand", default="")
    add_parser.add_argument("--barcode", default="")

    update_parser = commands.add_parser("update", help="Update an item's name, price, or stock")
    update_parser.add_argument("id", type=int)
    update_parser.add_argument("--name")
    update_parser.add_argument("--price", type=float)
    update_parser.add_argument("--stock", type=int)

    delete_parser = commands.add_parser("delete", help="Delete an inventory item")
    delete_parser.add_argument("id", type=int)

    find_parser = commands.add_parser("find", help="Find a product on OpenFoodFacts")
    # A mutually exclusive group requires either barcode or name, but not both.
    find_group = find_parser.add_mutually_exclusive_group(required=True)
    find_group.add_argument("--barcode")
    find_group.add_argument("--name")

    import_parser = commands.add_parser("import", help="Find and add an OpenFoodFacts product")
    import_group = import_parser.add_mutually_exclusive_group(required=True)
    import_group.add_argument("--barcode")
    import_group.add_argument("--name")
    import_parser.add_argument("--price", type=float, default=0.0)
    import_parser.add_argument("--stock", type=int, default=0)

    return parser


def main(argv=None):
    # parse_args converts command-line text into values on the args object.
    args = build_parser().parse_args(argv)

    # Each command below maps to one REST API method and route.
    if args.command == "list":
        return request_api("GET", "/inventory", args.api_url)
    if args.command == "get":
        return request_api("GET", f"/inventory/{args.id}", args.api_url)
    if args.command == "add":
        data = {
            "product_name": args.name,
            "price": args.price,
            "stock": args.stock,
            "brands": args.brand,
            "barcode": args.barcode,
        }
        return request_api("POST", "/inventory", args.api_url, json=data)
    if args.command == "update":
        # Include only options the user actually supplied.
        data = {
            key: value
            for key, value in {
                "product_name": args.name,
                "price": args.price,
                "stock": args.stock,
            }.items()
            if value is not None
        }
        if not data:
            print("Provide --name, --price, or --stock to update.", file=sys.stderr)
            return 1
        return request_api("PATCH", f"/inventory/{args.id}", args.api_url, json=data)
    if args.command == "delete":
        return request_api("DELETE", f"/inventory/{args.id}", args.api_url)
    if args.command == "find":
        # Query parameters belong in the URL instead of the JSON request body.
        params = {
            key: value
            for key, value in {"barcode": args.barcode, "name": args.name}.items()
            if value
        }
        return request_api("GET", "/products/search", args.api_url, params=params)

    # Import is the only remaining command after the earlier checks return.
    data = {
        "barcode": args.barcode,
        "name": args.name,
        "price": args.price,
        "stock": args.stock,
    }
    return request_api("POST", "/inventory/import", args.api_url, json=data)


# Return the main function's 0 (success) or 1 (error) as the program exit code.
if __name__ == "__main__":
    raise SystemExit(main())