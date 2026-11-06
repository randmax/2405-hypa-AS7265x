"""Compatibility entry point: both historical names launch the maintained GUI."""
if __name__ == "__main__":
    from bootstrap import bootstrap_or_exit
    bootstrap_or_exit()
    from mySpectRead02 import main
    main()
