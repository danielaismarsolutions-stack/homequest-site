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
| `language` | `nl` `en` `es` — not a question; it is the language the form was
displayed in (the `/nl` or `/es` page, `?lang=`, or the EN/NL/ES toggle), so it is
always present and never `fr`. The workflow still maps `fr` in case a French form
is added later. |
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

**1. Google Sheet** — `Sheet1` currently ends at column R (`ALONE?`). Add six
headers in the next free cells, spelled exactly as below. The node matches on
header text rather than position, but it fails outright on a column it cannot
find.

| Cell | Header |
| --- | --- |
| S1 | `LANGUAGE` |
| T1 | `PROFESSION` |
| U1 | `GROSS INCOME` |
| V1 | `AREA` |
| W1 | `RING` |
| X1 | `REFERRED BY` |

The 18 existing headers stay as they are, and the new ones must go at the end
in that order: the node stores a schema list that n8n compares against the
header row **positionally**, so a column inserted in the middle (or listed in a
different order in the export) fails the run with *"Column names were updated
after the node's setup"*. If you do move a column, open the node in n8n and
refresh the columns list rather than editing the JSON. `OCCUPATION` (F) now receives the
situation answer and `ALONE?` (R) the household answer, so the two renamed form
fields land in the columns they always did.

Values stay consistent with the rows already in the sheet: `HOME TYPE` still
writes `Studio` / `1br` / `2br` / `3br+` (plus the new `House`), and `DURATION`
still writes `Long term` for the longest option. The one value that changes is
`FURNISHED`, where the old ambiguous `None` becomes `No preference`.

**2. Monday renting board** — add a column for each new answer, then paste its
id into `RENT_COLUMNS` at the top of the **Normalize Lead Data** node:

    language · grossIncome · neighbourhood · ring · referralName

Any id left as `''` is simply skipped, so the node keeps writing every other
column until you get to it. Note that `text_mkt1wp59` used to receive a second
copy of the occupation answer and now receives *profession or studies* — check
that this is the column you want it in.
