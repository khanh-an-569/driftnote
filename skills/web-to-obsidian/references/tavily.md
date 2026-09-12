# Tavily fallback

Use Tavily only for public HTTP(S) URLs. The helper reads `TAVILY_API_KEY` from the process environment.

## Extraction policy

- Start with `basic` and `format=markdown`.
- Retry `advanced` at most once when basic extraction fails, returns too little content, or misses important tables or embedded material.
- A URL in `failed_results` is a failed extraction even when the HTTP request itself succeeded.
- Preserve the original URL and record the final extraction method.
- Fall back to a link-only note when both attempts fail.

Do not send Tavily:

- localhost, private IPs, `file:` URLs, or `.local` hosts;
- signed-in, personalized, internal, or paywalled URLs;
- selections copied from private pages;
- URLs containing credentials or sensitive query parameters.

Use Search only to verify claims or locate a canonical public source. Do not use Crawl, Map, or Research for routine capture.

Never place an API key in a skill file, note, command argument, URL, log, screenshot, or committed configuration. If a key may have leaked, stop and tell the user to revoke it.

Official references:

- https://docs.tavily.com/documentation/api-reference/endpoint/extract
- https://docs.tavily.com/documentation/best-practices/api-key-management
