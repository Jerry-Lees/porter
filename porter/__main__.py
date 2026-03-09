"""Entry point — `python -m porter` or the `porter` console script."""

from porter.app import PorterApp


def main() -> None:
    app = PorterApp()
    app.run()


if __name__ == "__main__":
    main()
