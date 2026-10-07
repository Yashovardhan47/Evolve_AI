# Progress and next steps

## Release 1 — implemented

The account-owned personal development loop, responsive interface, personal profile, state aggregation, adaptive recommendation ranking, goals/habits, interest-based daily tasks, recurring routines, daily reflections, financial awareness, randomized routine experiments, arithmetic scenarios, reminders, data controls and feedback capture are working end to end. Task estimates reserve development time and the dashboard shows daily progress and overload.

## Strongest advanced direction

Build a **personal evidence engine**: help each person choose routines they value, test small changes, and keep what is useful within their actual time and money constraints. This is a proposed product/research direction, not a claim of global novelty or proven wellbeing improvement. Ordinary task lists, habit tracking and AI task breakdown already exist in products such as [Habitica](https://habitica.com/) and [Tiimo](https://www.tiimoapp.com/product).

| Priority | Proposed addition | Concrete everyday benefit | How to evaluate it |
| --- | --- | --- | --- |
| 1 | Capacity-aware routine variants | User chooses normal/light/rest-day capacity; a 30-minute activity has a user-approved 5-minute alternative. Preserve essential commitments and leave spare time. | Compare with the current time-only planner: user edits, overload, follow-through and reported burden. |
| 2 | Personal routine experiments with a weekly review | Extend existing A/B sessions with a predefined question, chosen outcome, missed-session reporting and uncertainty. Example: which study time is easier to maintain? | Report sample size, missing days, routine usefulness and completion. Avoid causal conclusions from correlations or small informal samples. |
| 3 | Time, cost and energy tradeoffs across life areas | A person can compare a free walk, paid class or study session against their own budget, schedule and interests, then approve the choice. | Feasible plans, budget-rule violations, overrides and usefulness; no investment or clinical outcome prediction. |
| 4 | A private reflection coach with cited resources | Convert the person's own journal/learning material into a proposed small task; show the source and ask the user to save it. Support Telugu/Hindi/English and explicit consent for external model use. | Citation support, task accuracy, language usability, latency/cost and whether users accept or edit the task. |
| 5 | A personal progress story | Weekly review of wins, satisfaction, connection and routines the user wants to change. Show neglected areas as optional invitations, without a single personality or happiness score. | Voluntary satisfaction/agency ratings, helpfulness, burden and returning usage; keep missing responses visible. |
| 6 | Reliable mobile daily use | Installable PWA, offline capture with conflict-aware sync, calendar planning, verified accounts and user-controlled background reminders with quiet hours. | Offline/reconnect integrity, cross-device consistency, reminder delivery and opt-out behavior. |

Research on [just-in-time adaptive interventions](https://pmc.ncbi.nlm.nih.gov/articles/PMC5364076/) motivates using current context and receptivity when offering support. [Micro-randomized trials](https://arxiv.org/abs/2107.03544) describe designs for evaluating which intervention components help under which conditions. The current app's small personal A/B feature is not a full micro-randomized trial or a validated treatment.

Choose one main research question: **Does a user-controlled planner that adapts to capacity and routine feedback reduce perceived burden while maintaining valued activities, compared with fixed suggestions?** Start with a consenting pilot, predefined outcomes, an appropriate comparison, missing-data reporting and a sample-size justification. Publish measured limitations along with results. A four-week feasibility pilot can surface usability and retention issues; it does not by itself establish effectiveness.

## Next implementation priorities

1. Deploy the Python service with persistent storage and HTTPS; invite a small consenting pilot group.
2. Add verified email and password recovery before broader account adoption.
3. Add user-controlled background reminders through a real delivery provider, with quiet hours and unsubscribe controls.
4. Measure usefulness and consistency rather than assuming the app improves lives. Compare the adaptive ranker against a fixed-rule baseline, track adherence and burden, and obtain informed consent for any research data.
5. Add a validated personality questionnaire only after choosing a suitable licensed instrument. Keep trait dimensions separate from wellbeing and productivity; never score personal worth.
6. Move to PostgreSQL with explicit migrations for multiple application instances. Add encrypted storage/backups, monitoring and access auditing.
7. Add consented wearable/calendar connectors and optional AI language assistance. Clearly show what information leaves the user's account and preserve a local baseline when external models are unavailable.
8. Evaluate an individual predictive model only after sufficient longitudinal observations exist. Add calibration and uncertainty before any predictive what-if simulation. A causal graph must be treated as a hypothesis until supported by appropriate evidence.

## Research claims

An integration of a personal state model, contextual planning and feedback-driven ranking is a testable project direction. This repository does not prove global novelty, publication acceptance, treatment effectiveness, improved financial outcomes or a completed clinical digital twin. Publication claims require a literature review, a defined study and evaluation against meaningful baselines.
