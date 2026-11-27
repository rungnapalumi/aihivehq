# AIHive Leadership — future architecture (design only)

Status: **design proposal, not implemented.** The MVP stores only corporate inquiries
(`leadership_inquiries`, see `leadership/inquiry.py`). Everything below is a target model for
later phases, to keep today's choices compatible with it.

## Principles

1. **Consent first.** GPS tracks, coach observations and reports are personal data. Each is linked
   to a `consent_record` with purpose, scope, version and withdrawal date. No collection without it.
2. **Least access.** Participants see their own data; coaches see their assigned cohort; client HR
   sees only aggregated, anonymised results unless the participant opts in; partners see only
   operational data (schedules, headcount, payouts).
3. **Retention by default.** Every personal-data table has `retain_until`; a scheduled job deletes or
   anonymises expired rows. Suggested defaults: raw GPS 90 days, observations and reports 24 months.
4. **Human oversight.** AI-generated narrative is a draft until a certified coach approves it
   (`report.status = draft → coach_reviewed → released`). Scores stay illustrative unless and until
   a validated instrument is introduced.
5. **No live AI navigation in competitions.** Data from regulated orienteering events is imported
   after the event only (`gps_activity.source = 'post_event_import'`); the platform offers no
   real-time route advice during sanctioned competitions.
6. **Multi-tenant.** Every business row carries `organization_id` so one deployment serves many
   corporate clients and partners (aligned with the AIHiveHQ multi-client plan).

## Entities

```
organization (id, type: client|sports_partner|aihivehq, name, country, billing_contact_id, created_at)
person (id, organization_id, full_name, email, phone, locale, created_at)
consent_record (id, person_id, purpose: program|gps|observation|report_sharing|marketing,
                policy_version, granted_at, withdrawn_at, evidence)

coach (id, person_id, certifications_json, verified_at, languages, active)
sports_partner (id, organization_id, discipline: orienteering|..., region, safety_officer_person_id,
                revenue_share_pct, payout_account_ref)

program (id, code: expedition|executive_simulation|team_transformation, name, version, status)
mission_template (id, program_id, code: strategic_navigator|uncertainty|distributed|ceo_challenge,
                  version, competencies_json, rules_json, rubric_json)
expedition (id, program_id, client_org_id, partner_org_id, venue, starts_at, ends_at,
            status: draft|confirmed|completed|cancelled, map_ref)
expedition_mission (id, expedition_id, mission_template_id, order_index, params_json)

team (id, expedition_id, name)
participant (id, person_id, expedition_id, team_id, role_rotation_json, consent_bundle_id)
coach_assignment (id, expedition_id, coach_id, team_id)

gps_activity (id, participant_id, expedition_mission_id, source: device|app|post_event_import,
              started_at, ended_at, track_ref /* object storage key, encrypted */, retain_until)
decision_event (id, participant_id|team_id, expedition_mission_id, occurred_at, decision_code,
                option_code, rationale_text, recorded_by: participant|coach|system)
coach_observation (id, coach_id, participant_id, expedition_mission_id, observed_at,
                   competency_code, behaviour_text, evidence_ref, retain_until)

leadership_report (id, participant_id, expedition_id, rubric_version, scores_json /* illustrative */,
                   narrative_draft, narrative_model, status: draft|coach_reviewed|released,
                   reviewed_by_coach_id, released_at, retain_until)
action_plan (id, report_id, items_json, coach_followup_at, aihive_coach_link_token)

booking (id, expedition_id, client_org_id, seats, status, quote_ref, created_at)
payment (id, booking_id, provider: stripe, provider_ref, amount_minor, currency, status, paid_at)
revenue_share (id, payment_id, partner_org_id|coach_id, basis: pct|fixed, amount_minor, status,
               payout_ref, settled_at)
leadership_inquiry (existing MVP table — becomes the top of the sales funnel → booking)
```

## How the MVP maps onto this

| MVP element | Future entity |
|---|---|
| `sim.js` `DECISIONS` / options | `mission_template.rules_json` |
| `sim.js` rubric indicators | `mission_template.rubric_json` (versioned → `leadership_report.rubric_version`) |
| Demo decision history | `decision_event` |
| Demo report object | `leadership_report.scores_json` + `action_plan.items_json` |
| `leadership_inquiries` table | `leadership_inquiry` → `booking` |
| Stripe test checkout in PR #19 (coach booking) | `payment` (same provider, shared integration) |

## Suggested delivery order

1. Persistent database (Render Postgres or the existing AIHive DB plan) + tested inquiry email.
2. Coach console: create an expedition, record `decision_event` and `coach_observation` on mobile.
3. Report pipeline with coach review gate; optional AI narrative grounded only in recorded events.
4. Booking + payment + partner revenue share.
5. GPS import (post-event only) with explicit consent and retention jobs.
