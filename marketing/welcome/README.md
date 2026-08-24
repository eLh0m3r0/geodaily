# Welcome sequence — Buttondown setup

Welcome emails are the single highest-leverage retention tool we are not using:
they open at 51–69 % (vs 20–40 % for regular sends), and a multi-email series
lifts engagement up to 51 % (Klaviyo/Omnisend 2025–26). Buttondown supports
this natively via **Settings → Automations** (no code needed).

## Setup (once, ~10 minutes)

1. In Buttondown: **Settings → Automations → New automation**
   - Trigger: *Subscriber confirms their subscription*
   - Action: *Send email* → paste `01-welcome.md` (send immediately)
2. Second automation: same trigger, delay **3 days** → paste `02-how-to-read.md`
3. Third automation: same trigger, delay **10 days** → paste `03-survey.md`
4. In **Settings → Subscribing**, make sure double opt-in is ON (cleaner list,
   better deliverability).
5. Set the sender name to a personal one (e.g. `"<your name> — Geopolitical
   Daily"`): personal sender names open ~4 % better than institutional ones
   (MailerLite, 20k campaigns, 2025). Also set the `NEWSLETTER_EDITOR_NAME`
   GitHub secret/variable so the newsletter footer names the same person.

## Frequency tags

The subscribe forms on the site post a `tag` field: subscribers who pick
"Weekly digest" arrive tagged `weekly` (see `BUTTONDOWN_WEEKLY_TAG`).
The daily send excludes that tag and the Sunday digest targets it — no
manual work needed. When someone replies "weekly" to a daily email, add the
`weekly` tag to their subscriber record by hand (Subscribers → edit → tags).

Placeholders in the drafts: replace `{{EDITOR_NAME}}` before pasting, or keep
Buttondown's own template variables where noted.
