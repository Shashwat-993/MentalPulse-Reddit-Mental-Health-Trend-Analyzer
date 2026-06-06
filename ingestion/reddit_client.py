"""PRAW client wrapper: authentication, rate-limit handling, and local caching.

Implemented in Phase 1. Responsibilities:
  * Authenticate via .env (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT) — public, read-only access only.
  * Send a descriptive, ToS-compliant User-Agent.
  * Rely on PRAW's built-in rate-limit backoff; add a simple on-disk cache so
    re-runs don't re-fetch the same posts.

Responsible-use guardrails (see README "Responsible Data Use"):
  * Public subreddits only — never private subreddits, DMs, or authed-user data.
  * Non-commercial, research/portfolio use; respect Reddit API ToS.
"""

from __future__ import annotations

from pathlib import Path

from config.loader import Config


class RedditClient:
    """Thin wrapper around a read-only PRAW ``Reddit`` instance.

    Wires auth from config/secrets and provides cached access to listings.
    Fully implemented in Phase 1.
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.cache_dir = Path(cfg.reddit.cache_dir)
        # TODO(Phase 1): validate secrets and construct the PRAW client, e.g.
        #   cfg.secrets.require(
        #       "reddit_client_id", "reddit_client_secret", "reddit_user_agent"
        #   )
        #   self._reddit = praw.Reddit(
        #       client_id=cfg.secrets.reddit_client_id,
        #       client_secret=cfg.secrets.reddit_client_secret,
        #       user_agent=cfg.secrets.reddit_user_agent,
        #       check_for_async=False,
        #   )
        raise NotImplementedError("RedditClient is implemented in Phase 1.")

    def fetch_listing(self, subreddit: str, listing: str, limit: int):
        """Yield submissions from a subreddit listing (e.g. 'top', 'new')."""
        raise NotImplementedError("Implemented in Phase 1.")
