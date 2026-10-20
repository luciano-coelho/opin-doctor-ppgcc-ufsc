#!/usr/bin/env python3
"""Reads stdin line by line, masks AWS account IDs and ARNs, writes to
stdout immediately (line-buffered, so it's safe to pipe a live,
streaming command through it without losing real-time visibility).

Found live, this project's own session: an `AccessDeniedException`
from a denied AWS API call (`pricing:DescribeServices`) printed this
project's full IAM ARN -- account ID included
(`arn:aws:iam::<12 digits>:user/...`) -- in a tool-call result, simply
because IAM denial messages always embed the full ARN of the caller.
Terraform's own error output (a failed `apply`/`destroy`/`plan`) can do
the same for any AWS-sourced error. Neither is a secret in the
cryptographic sense, but this project's own standing rule is that the
account ID is never printed or committed -- so every AWS-adjacent
command's error output gets piped through this filter before a human
or a log file ever sees it, not trusted to not happen to mention it.

Usage:
  some-aws-command 2>&1 | python3 redact_aws_errors.py

Two patterns, deliberately broad rather than narrow:
  1. Any "arn:aws:..." token (ARNs always carry the account ID as their
     5th colon-separated field, among other sensitive detail) --
     masked whole, not just the account-ID portion.
  2. Any standalone 12-digit number (AWS account IDs are always
     exactly 12 digits) -- catches a bare account ID mentioned outside
     an ARN (e.g. "Account 123456789012 is not authorized...").
     A false positive here (masking an unrelated 12-digit number that
     happens to appear in some other error text) costs nothing --
     this filter runs ONLY on already-failed/error output a human is
     reading to diagnose a problem, never on data that itself matters.
"""
import re
import sys

_ARN_RE = re.compile(r"arn:aws:[^\s\"'<>]*")
_ACCOUNT_ID_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")


def redact(text: str) -> str:
    text = _ARN_RE.sub("arn:aws:<REDACTED>", text)
    text = _ACCOUNT_ID_RE.sub("<REDACTED-ACCOUNT-ID>", text)
    return text


def main() -> None:
    for line in sys.stdin:
        sys.stdout.write(redact(line))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
