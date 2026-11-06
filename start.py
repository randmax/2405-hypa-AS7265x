"""Cross-platform entry point. No manual virtualenv activation is required."""

from bootstrap import bootstrap_or_exit

if __name__ == "__main__":
    bootstrap_or_exit()
    from mySpectRead02 import main
    main()
