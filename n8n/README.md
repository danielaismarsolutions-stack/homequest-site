# n8n — HomeQuest lead workflow

`homequest-lead.workflow.json` is the workflow behind
`https://n8n.srv1037212.hstgr.cloud/webhook/homequest-lead`, the endpoint the
intake modal on this site posts to. Import it in n8n (**Workflows → Import from
File**) and reconnect the three credentials (Gmail, Google Sheets, Monday.com) —
credential IDs travel with the export but the OAuth grants do not.

This version matches the rent form as it stands in `index.html`. The buy form,
and everything the workflow does with it, is unchanged.

## What the rent form now sends

| Field | Values |
| --- | --- |
| `language` | `nl` `en` `fr` `es` |
| `situation` | `employed` `self_employed` `student` `other` (was `occupation`) |
| `profession` | free text |
| `gross_income` | number, € per month, combined for a couple |
| `household` | `single` `couple` `sharing` (was `living`) |
| `search_city_other` | free text, only when `search_city` is `Other` |
| `ams_ring` | `inside` `outside` `no_preference`, only for Amsterdam |
| `search_area` | free text, optional |
| `furnished` | `yes` `no` `no_preference` |
| `home_type` | `studio` `1br` `2br` `3br+` `house` |
| `referral_name` | free text, only for `referral` / `employee` sources |
| `source` | now also `chatgpt` and `tiktok`; optional |
| `duration`, `about` | optional |

Payloads from the previous form still normalise correctly (`occupation`,
`living`, and the old `furnished` values are all still recognised), so replaying
an old execution or a queued submission will not break.

## Two manual steps after importing

**1. Google Sheet** — add these headers to `Sheet1`, or the append node will
fail on an unknown column:

    LANGUAGE · PROFESSION · GROSS INCOME · AREA · RING · REFERRED BY

`OCCUPATION` now receives the situation answer and `ALONE?` receives the
household answer, so both keep their existing headers.

**2. Monday renting board** — add a column for each new answer, then paste its
id into `RENT_COLUMNS` at the top of the **Normalize Lead Data** node:

    language · grossIncome · neighbourhood · ring · referralName

Any id left as `''` is simply skipped, so the node keeps writing every other
column until you get to it. Note that `text_mkt1wp59` used to receive a second
copy of the occupation answer and now receives *profession or studies* — check
that this is the column you want it in.
