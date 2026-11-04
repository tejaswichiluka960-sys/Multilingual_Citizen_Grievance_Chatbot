# AI complaint routing

When `ENABLE_AI_ROUTING=true` and `SARVAM_API_KEY` is configured, low-confidence
free-form complaints are sent to Sarvam's structured chat-completion endpoint.
The local keyword/Hugging Face classifier still handles confident complaints and
is the fallback when the provider is unavailable.

The application sends the selected language and original complaint text. Sarvam
must return a strict JSON object containing a department code, intent, priority,
confidence, clarification flag and short summary. The application validates the
department against the ten seeded database departments before a ticket can be
created. Unknown or ambiguous results remain in the clarification flow.

Keep `SARVAM_API_KEY` in `.env` only. Never commit it to GitHub. The provider
request is synchronous and has a bounded timeout controlled by
`AI_ROUTING_TIMEOUT_SECONDS`.
