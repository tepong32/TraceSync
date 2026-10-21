"""Always exit before main.py: this artifact must never become an ordinary app."""
from acceptance.cache_diagnostic import main

raise SystemExit(main())
