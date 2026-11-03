"""Launch the portable workbench MCP adapter without opening a repository."""

from workbench.mcp_stdio import main


if __name__ == "__main__":
    raise SystemExit(main())
