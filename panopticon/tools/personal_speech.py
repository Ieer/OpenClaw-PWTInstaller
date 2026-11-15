"""Compatibility CLI for deployments predating the shared agent_speech name."""

from agent_speech import main


if __name__ == "__main__":
    raise SystemExit(main())