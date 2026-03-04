"""Token management CLI for sh4r3d (DynamoDB backend).

Usage:
  python manage.py add-token [--label "Alice"]
  python manage.py list-tokens
  python manage.py revoke-token <token>

Requires AWS credentials in the environment (AWS_PROFILE, AWS_ACCESS_KEY_ID, etc.)
or a configured ~/.aws/credentials file.
"""
import argparse
import os
import secrets
import sys
import time

import boto3
from botocore.exceptions import ClientError


def _tokens_table():
    from app.config import settings
    kwargs = {}
    if endpoint := os.environ.get("AWS_ENDPOINT_URL"):
        kwargs["endpoint_url"] = endpoint
    return boto3.resource("dynamodb", region_name=settings.aws_region, **kwargs).Table(
        settings.dynamodb_table_tokens
    )


def cmd_add_token(args):
    token = secrets.token_urlsafe(24)
    _tokens_table().put_item(Item={
        "token": token,
        "label": args.label or "",
        "created_at": int(time.time()),
        "is_active": 1,
    })
    print(f"Token: {token}")
    if args.label:
        print(f"Label: {args.label}")


def cmd_list_tokens(args):
    items = sorted(
        _tokens_table().scan().get("Items", []),
        key=lambda x: int(x.get("created_at", 0)),
        reverse=True,
    )
    if not items:
        print("No tokens.")
        return
    print(f"{'Token':<36}  {'Label':<20}  Status")
    print("-" * 68)
    for item in items:
        status = "active" if int(item.get("is_active", 0)) == 1 else "revoked"
        print(f"{item['token']:<36}  {item.get('label', ''):<20}  {status}")


def cmd_revoke_token(args):
    try:
        _tokens_table().update_item(
            Key={"token": args.token},
            UpdateExpression="SET is_active = :zero",
            ConditionExpression="attribute_exists(#t)",
            ExpressionAttributeNames={"#t": "token"},
            ExpressionAttributeValues={":zero": 0},
        )
        print(f"Revoked: {args.token}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            print(f"Token not found: {args.token}", file=sys.stderr)
            sys.exit(1)
        raise


def main():
    parser = argparse.ArgumentParser(description="sh4r3d token management")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("add-token", help="Generate and store a new invite token")
    p.add_argument("--label", help="Human-readable label (e.g. 'Alice')")

    sub.add_parser("list-tokens", help="List all tokens")

    p = sub.add_parser("revoke-token", help="Revoke a token")
    p.add_argument("token", help="The token string to revoke")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {
        "add-token": cmd_add_token,
        "list-tokens": cmd_list_tokens,
        "revoke-token": cmd_revoke_token,
    }[args.command](args)


if __name__ == "__main__":
    main()
