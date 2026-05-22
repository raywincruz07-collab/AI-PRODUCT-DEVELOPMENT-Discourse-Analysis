"""Keyword frequency and extraction analysis."""

import re
from collections import Counter
from database.connection import get_backend, get_conn

# Common English stopwords (avoids NLTK dependency)
STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "is",
    "it",
    "its",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "our",
    "their",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "because",
    "as",
    "until",
    "while",
    "about",
    "between",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "up",
    "down",
    "out",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "any",
    "if",
    "around",
    "ever",
    "never",
    "every",
    "across",
    "within",
    "without",
    "among",
    "upon",
    "along",
    "behind",
    "toward",
    "towards",
    "whether",
    "despite",
    "except",
    "though",
    "already",
    "always",
    "often",
    "since",
    "where",
    "when",
    "whereas",
    "into",
    "also",
    "get",
    "got",
    "like",
    "dont", "didnt", "didn", "doesn", "doesnt", "wasn", "wasnt",
    "hasn", "hasnt", "haven", "havent", "isn", "isnt", "aren", "arent",
    "weren", "werent", "wouldn", "wouldnt", "couldn", "couldnt",
    "shouldn", "shouldnt", "mustn", "mustnt", "needn", "wont",
    "im", "ive", "ive", "ill", "id", "wed", "weve", "theyd", "theyre",
    "theyve", "hes", "shes", "whos", "whats", "theres", "heres",
    "thats", "its",
    "going",
    "really",
    "one",
    "even",
    "much",
    "well",
    "back",
    "still",
    "way",
    "make",
    "know",
    "think",
    "see",
    "go",
    "come",
    "take",
    "want",
    "look",
    "use",
    "find",
    "give",
    "tell",
    "say",
    "said",
    "new",
    "now",
    "people",
    "time",
    "right",
    "good",
    "http",
    "https",
    "www",
    "com",
}

# Extra noise words for velocity spike alerts only.
# These pass the basic stopword filter but carry no news value when spiking —
# they reflect generic conversation patterns, not newsworthy events.
SPIKE_NOISE_WORDS = {
    # Internet slang / filler reactions
    "lol", "lmao", "lmfao", "omg", "wtf", "smh", "bruh", "bro",
    "yall", "gonna", "wanna", "gotta", "kinda", "sorta",
    "tbh", "imo", "imho", "fyi", "btw", "idk", "irl",
    "haha", "hehe", "yeah", "yep", "nope", "nah", "okay",
    "woah", "whoa", "damn", "dude", "mate", "babe", "guys",
    # Generic filler verbs (describe activity, not events)
    "need", "feel", "felt", "make", "made", "take", "took",
    "keep", "kept", "mean", "means", "seem", "seems", "lets",
    "call", "talk", "told", "says", "said", "asks", "asked",
    "used", "using", "found", "gets", "getting", "trying",
    "tried", "starts", "wants", "needs", "puts", "done",
    "went", "came", "comes", "goes", "move", "moves",
    "watch", "watched", "watching", "work", "works", "worked",
    "live", "lived", "lives", "living", "play", "plays", "played",
    "run", "runs", "running", "ran", "set", "sets", "setting",
    "let", "lets", "letting", "put", "puts", "putting",
    # Generic degree / sentiment words that are not events
    "great", "good", "best", "bad", "worse", "worst", "better",
    "sure", "true", "real", "hard", "easy", "open", "free",
    "able", "full", "next", "last", "late", "early", "past",
    "whole", "else", "maybe", "perhaps", "likely", "simply",
    "actually", "literally", "basically", "exactly", "clearly",
    "quickly", "finally", "usually", "sometimes", "recently",
    "currently", "generally", "certainly", "definitely",
    "absolutely", "completely", "obviously", "apparently",
    "pretty", "quite", "rather", "truly", "highly", "totally",
    "seriously", "honestly", "probably", "wrong", "correct",
    # Social media / web meta-words
    "thread", "reply", "replies", "comment", "comments",
    "share", "shares", "link", "links", "click", "clicks",
    "tweet", "tweets", "retweet", "account", "accounts",
    "video", "videos", "image", "images", "photo", "photos",
    "meme", "memes", "content", "message", "messages",
    "email", "website", "source", "sources", "post", "posts",
    # Generic time words (not specific enough to be newsworthy)
    "today", "yesterday", "tomorrow", "week", "weeks",
    "month", "months", "year", "years", "hour", "hours",
    "minute", "minutes", "days", "times", "since", "soon",
    "twice", "daily", "weekly", "monthly", "yearly",
    # Vague generic nouns
    "thing", "things", "stuff", "something", "anything",
    "everything", "nothing", "someone", "anyone", "everyone",
    "nobody", "somebody", "everybody", "person", "persons",
    "part", "parts", "place", "places", "case", "cases",
    "point", "points", "fact", "facts", "idea", "ideas",
    "reason", "reasons", "kind", "type", "side", "hand",
    "life", "word", "words", "form", "forms",
    "example", "examples", "level", "levels", "line", "lines",
    "name", "names", "step", "steps", "situation", "moment",
    "story", "stories", "account", "accounts", "view", "views",
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    # Generic nouns from news/journalism (too broad to signal a topic)
    "house", "public", "country", "issue", "issues",
    "social", "articles", "article",
    "page", "pages", "site", "sites",
    "official", "officials", "officer", "officers",
    "report", "reports", "reporting",
    "response", "responses", "process", "processes",
    "action", "actions", "plan", "plans",
    "group", "groups", "power", "powers",
    "role", "roles", "order", "orders",
    "claim", "claims", "question", "questions",
    "problem", "problems", "concern", "concerns",
    "decision", "decisions", "position", "positions",
    "system", "systems", "program", "programs",
    "policy", "policies", "effort", "efforts",
    "impact", "impacts", "effect", "effects",
    "result", "results", "outcome", "outcomes",
    "change", "changes", "increase", "increases",
    "number", "numbers", "amount", "amounts",
    "area", "areas", "field", "fields",
    "member", "members", "leader", "leaders",
    "force", "forces", "right", "rights",
    "move", "moves", "statement", "statements",
    "information", "detail", "details",
    "another", "others", "amid",
    # Generic verbs that slip past stopwords
    "become", "became", "becomes",
    "include", "includes", "included",
    "continue", "continues", "continued",
    "remain", "remains", "remained",
    "appear", "appears", "appeared",
    "provide", "provides", "provided",
    "receive", "receives", "received",
    "follow", "follows", "followed",
    "allow", "allows", "allowed",
    "help", "helps", "helped",
    "hold", "holds", "held",
    "face", "faces", "faced",
    "leave", "leaves", "left",
    "lead", "leads", "leading",
    "turn", "turns", "turned",
    "raise", "raises", "raised",
    "bring", "brings", "brought",
    "describe", "described", "describes",
    "consider", "considered", "considers",
    "expect", "expected", "expects",
    # Journalistic boilerplate verbs
    "says", "said", "told", "added", "noted", "warned",
    "urged", "argued", "suggested", "questioned", "called",
    "wrote", "writes", "write", "written",
    "seen", "known", "given", "taken", "made", "said",
    "used", "called", "named", "based", "found",
    # Sentence connectors / transitional words (carry no topical signal)
    "including", "according", "despite", "however", "therefore", "although",
    "whereas", "nevertheless", "furthermore", "meanwhile", "moreover",
    "following", "regarding", "within", "without", "through", "against",
    "among", "during", "based", "related", "first", "second", "third",
    "latest", "recent", "earlier", "later", "former", "latter", "already",
    "reported", "stated", "claimed", "announced", "confirmed", "denied",
    # Common discourse filler
    "show", "state", "staff", "news", "read", "shot",
    "saying", "making", "taking", "talking", "looking",
    "happening", "working", "coming", "going", "being",
    "having", "doing", "thinking", "telling", "asking",
    # Generic adjectives / quantities not in base stopwords
    "important", "significant", "possible", "possible",
    "similar", "specific", "particular", "necessary",
    "special", "general", "common", "possible",
    "world", "old", "high", "low", "long", "big", "large", "small",
    "many", "several", "various", "always", "never", "often",
    "major", "minor", "little", "different",
    "day", "night", "morning", "evening", "week", "ago",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
}

# Profanity / obscenity — filtered across all platforms
_PROFANITY = {
    "fuck", "fucking", "fucked", "fucker", "fuckers", "fucks",
    "shit", "shits", "shitting", "shitty",
    "ass", "asses", "asshole", "assholes",
    "bitch", "bitches", "bitching",
    "crap", "crappy", "cunt", "cunts",
    "dick", "dicks", "pussy", "pussies",
    "cock", "cocks", "balls", "piss", "pissed",
    "bastard", "bastards", "wanker", "wankers",
    "bullshit", "horseshit",
    "retard", "retarded", "retards",
    "faggot", "faggots", "nigger", "niggers",
}

# 4chan-specific slang — meaningless outside the platform
_FOURCHAN_SLANG = {
    "kek", "lmao", "kekked", "based", "cope", "seethe", "cringe",
    "glowie", "glowies", "anon", "anons", "sage", "moot", "trips",
    "dubs", "quads", "gets", "checked", "incel", "simp",
    "chad", "gigachad", "normie", "normies", "redpill", "bluepill",
    "blackpill", "pilled", "woke", "shitpost", "shitposting",
    "greentext", "copypasta", "pasta", "slide", "shill", "shills",
    "shilling", "psyop", "psyops", "digits", "kys", "rent", "free",
    "touch", "grass", "ratio", "unbased", "ngmi", "wagmi",
    "fren", "frens", "reeee", "reee",
}

# Mastodon/Fediverse-specific terms — platform mechanics not news
_MASTODON_SLANG = {
    "toot", "toots", "tooted", "tooter", "boost", "boosted", "boosting",
    "boosts", "fediverse", "federated", "federation", "instance",
    "instances", "mastodon", "pleroma", "misskey", "pixelfed",
    "reblog", "reblogs", "reblogged", "mention", "mentions",
    "mentioned", "follower", "followers", "following", "unfollow",
    "masto", "fedi", "activitypub",
}

# HTML artifacts that survive stripping
_HTML_ARTIFACTS = {
    "amp", "nbsp", "quot", "apos", "href", "src", "html", "http",
    "https", "www", "com", "org", "net", "png", "jpg", "jpeg",
    "gif", "webp", "svg", "css", "div", "span", "class", "style",
    "onclick", "script", "iframe", "embed",
    "rss", "xml", "json", "api", "url", "uri",
}

# Generic words that pass the existing filters but add no news signal when spiking
_ADDITIONAL_GENERIC = {
    # Past tense of already-filtered verbs
    "knew", "came", "bore", "wore", "tore", "swore", "grew", "drew",
    "flew", "threw", "blew", "show", "knew", "read",
    # Generic movement / direction
    "walk", "walks", "walked", "walking", "away", "near",
    # Generic locations / objects (no news value standalone)
    "home", "door", "room", "wall", "yard", "hall", "roof", "lawn",
    "road", "path", "park", "desk", "seat", "chair", "floor",
    # Generic emotions / sentiments (too vague to signal a topic)
    "love", "loved", "loves", "loving",
    "hate", "hated", "hates", "hating",
    "hope", "hoped", "hopes", "hoping",
    "glad", "calm", "dull", "mild", "bold",
    "loud", "huge", "tiny", "ugly", "rude",
    # Tech/platform metadata (not editorial news)
    "code", "data", "file", "user", "list", "item", "type",
    "mode", "sort", "form", "grid", "view", "menu",
    # Extra generic nouns commonly seen in online text
    "chat", "feed", "news", "blog", "wiki", "copy", "edit",
    "draft", "save", "load", "open", "close", "send", "sync",
    # Misc short generic words not in other lists
    "else", "ever", "self", "each", "once", "both", "much", "such",
    "from", "with", "that", "this", "them", "then", "thus",
    "into", "onto", "upon", "over", "under", "above", "below",
    # Extra sentence filler
    "also", "even", "very", "just", "only", "well", "back",
    "down", "away", "more", "less", "most", "some", "many",
    "long", "high", "wide", "deep", "fast", "slow", "full",
    "dark", "warm", "cool", "cold", "loud", "soft", "hard",
}

SPIKE_NOISE_WORDS = SPIKE_NOISE_WORDS | _FOURCHAN_SLANG | _MASTODON_SLANG | _HTML_ARTIFACTS | _PROFANITY | _ADDITIONAL_GENERIC


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, filtering stopwords and noise."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if len(w) > 3 and w not in STOPWORDS and w not in SPIKE_NOISE_WORDS]


async def get_top_keywords(
    platform: str = None, start: str = None, end: str = None, n: int = 50
) -> list[dict]:
    """Get the most frequent keywords in posts."""
    backend = get_backend()

    if backend == "sqlite":
        where = []
        params = []
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if start:
            where.append("posted_at >= ?")
            params.append(start)
        if end:
            where.append("posted_at <= ?")
            params.append(end)

        where_sql = " AND ".join(where) if where else "1=1"
        async with get_conn() as conn:
            cur = await conn.execute(
                f"SELECT content_text FROM posts WHERE {where_sql}", params
            )
            rows = await cur.fetchall()

        counter = Counter()
        for row in rows:
            counter.update(tokenize(row[0]))
        return [{"keyword": k, "count": c} for k, c in counter.most_common(n)]

    where = []
    params = []
    i = 1
    if platform:
        where.append(f"platform = ${i}")
        params.append(platform)
        i += 1
    if start:
        where.append(f"posted_at >= ${i}")
        params.append(start)
        i += 1
    if end:
        where.append(f"posted_at <= ${i}")
        params.append(end)
        i += 1

    where_sql = " AND ".join(where) if where else "TRUE"
    async with get_conn() as conn:
        rows = await conn.fetch(
            f"SELECT content_text FROM posts WHERE {where_sql}", *params
        )

    counter = Counter()
    for row in rows:
        counter.update(tokenize(row[0]))

    return [{"keyword": k, "count": c} for k, c in counter.most_common(n)]


async def get_keyword_frequency(
    keyword: str,
    platform: str = None,
    granularity: str = "day",
    start: str = None,
    end: str = None,
) -> list[dict]:
    """Get frequency of a specific keyword over time."""
    backend = get_backend()

    if backend == "sqlite":
        fmt_map = {"hour": "%Y-%m-%d %H:00", "day": "%Y-%m-%d", "week": "%Y-%W"}
        fmt = fmt_map.get(granularity, "%Y-%m-%d")

        where = ["content_text LIKE ?"]
        params = [f"%{keyword}%"]
        if platform:
            where.append("platform = ?")
            params.append(platform)
        if start:
            where.append("posted_at >= ?")
            params.append(start)
        if end:
            where.append("posted_at <= ?")
            params.append(end)

        where_sql = " AND ".join(where)
        async with get_conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT strftime('{fmt}', posted_at) as period, COUNT(*) as count
                FROM posts
                WHERE {where_sql}
                GROUP BY period
                ORDER BY period
                """,
                params,
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    period_expr = {
        "hour": "date_trunc('hour', posted_at)",
        "day": "date_trunc('day', posted_at)",
        "week": "date_trunc('week', posted_at)",
    }.get(granularity, "date_trunc('day', posted_at)")

    where = []
    params = []
    i = 1

    where.append(f"content_text ILIKE ${i}")
    params.append(f"%{keyword}%")
    i += 1

    if platform:
        where.append(f"platform = ${i}")
        params.append(platform)
        i += 1
    if start:
        where.append(f"posted_at >= ${i}")
        params.append(start)
        i += 1
    if end:
        where.append(f"posted_at <= ${i}")
        params.append(end)
        i += 1

    where_sql = " AND ".join(where) if where else "TRUE"

    async with get_conn() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {period_expr} AS period, COUNT(*)::int AS count
            FROM posts
            WHERE {where_sql}
            GROUP BY period
            ORDER BY period
            """,
            *params,
        )

    return [
        {"period": r["period"].isoformat(sep=" "), "count": r["count"]} for r in rows
    ]
