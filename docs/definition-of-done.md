# Definition of Done

Written before the work started; ticked at the end. A line is ticked only with evidence beside it.
Test command for every "test:" entry below:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps \
  -v "$PWD/cvat:/home/django/cvat" --entrypoint bash cvat_server \
  -c "pip install -q fakeredis[lua]==2.40.0 && DJANGO_SETTINGS_MODULE=cvat.settings.testing python manage.py test cvat.apps.test -v 2"
```

Test output: `<<FILL FROM MY MACHINE: last lines of the test run, e.g. "Ran N tests ... OK">>`

## Floor (items 1-4)

- [ ] **Endpoint returns correct counts, checked against a known task.**
  Code: `cvat/apps/test/counts.py`, `count_annotations_by_label`.
  Test: `CountAnnotationsByLabelTest.test_counts_match_hand_checked_values` (car 4, person 2; hand count in `tests/utils.py`, `populate_hand_checked_annotations`).
  Live check on COCO: endpoint count for `person` = `<<FILL>>`; same number from the source file = `<<FILL>>`, computed with
  `python -c "import json,collections as c;d=json.load(open('annotations/instances_val2017.json'));n={x['id']:x['name'] for x in d['categories']};print(c.Counter(n[a['category_id']] for a in d['annotations']).most_common(5))"`
  (equal only if every image was uploaded; with a subset, compare against the subset's images).
- [ ] **Counts come from a database aggregate, not from loading annotations.**
  Test: `test_number_of_queries_does_not_depend_on_annotation_count` (5 queries before and after adding shapes).
- [ ] **Edge cases decided and tested**: ground truth job excluded, deleted frame excluded, a track counts once, a skeleton counts once with its points not listed, project labels used for tasks in a project.
  Tests: `test_counts_match_hand_checked_values`, `test_skeleton_counts_once_and_its_points_are_not_listed`, `test_task_in_project_uses_project_labels`.
- [ ] **A page in the UI calls the endpoint.** Route `/tasks/:tid/annotation-counts` in `cvat-ui/src/components/cvat-app.tsx`; menu entry "Annotation counts" in `cvat-ui/src/components/tasks-page/actions-menu-items.tsx`.
  Screenshot / Loom timestamp: `<<FILL>>`
- [ ] **Counts shown as a graph.** `annotation-counts-chart.tsx` (horizontal bars, `react-chartjs-2`, already a dependency).
  Screenshot: `<<FILL>>`
- [ ] **Empty state**: a task with labels but no annotations shows "This task has no annotations yet".
  Screenshot: `<<FILL>>`
- [ ] **Failed request state with retry**: stop the server (`docker stop cvat_server`), open the page, see the error and the Retry button; start it again, press Retry, the chart appears.
  Screenshot: `<<FILL>>`
- [ ] UI checks: `npx eslint cvat-ui/src/components/annotation-counts-page/` and `cd cvat-ui && npx tsc --noEmit` both clean. Output: `<<FILL>>`

## Auth (item 5)

- [ ] **No login: 401.** Test `test_request_without_login_is_refused_with_401`. curl: `<<FILL: status line>>`
- [ ] **Logged in, no access to the task: 403.** Test `test_user_without_access_to_the_task_is_refused_with_403`. curl: `<<FILL>>`
- [ ] **Owner and assignee: 200.** Tests `test_task_owner_gets_the_counts`, `test_task_assignee_gets_the_counts`. curl: `<<FILL>>`
- [ ] Permission is CVAT's own tasks policy (`view:annotations`), not new auth code: `cvat/apps/test/permissions.py`.

## Objective (item 6)

- [ ] MO-1 written in the required format: `docs/objectives.md`.
- [ ] Measured 5 times, raw output saved in `docs/objectives.md`. `<<FILL: link to the section after pasting>>`
- [ ] Target met, or missed with the reason written down. `<<FILL: median vs 150 ms>>`
- [ ] Machine and CVAT commit recorded. `<<FILL>>`

## Filter / grouping (item 7)

- [ ] `?group_by=source` splits each label by how it was made. Test `test_group_by_source_splits_each_label`; invalid value is a 400, test `test_unknown_grouping_is_rejected_with_400`. Reason for the choice: `docs/plan.md`.
- [ ] Page switch "Per label / Per label and source" shows stacked bars. Screenshot: `<<FILL>>`

## Live updates (items 8-9)

- [ ] A save in the annotation editor publishes a change. Test `test_saving_annotations_in_the_editor_publishes_a_task_change` (goes through `PATCH /api/jobs/{id}/annotations`); unrelated task saves do not, `test_other_task_updates_do_not_publish`.
- [ ] Socket sends a snapshot, then a new one after a change. Test `test_socket_pushes_a_snapshot_and_then_every_change`.
- [ ] Socket refuses cross-origin (`test_cross_origin_handshake_is_rejected`), no login (4401) and no access (4403).
- [ ] Manual: two windows, draw a box and save in one, the chart in the other updates without reload. Loom timestamp: `<<FILL>>`
- [ ] Manual: `docker restart cvat_server` while the page is open; the tag goes "Reconnecting…" then "Live", and counts saved during the outage appear. Loom timestamp: `<<FILL>>`

## Docs and presentation (item 10)

- [ ] Plan committed first, with no code. `<<FILL: SHA of the first commit>>`
- [ ] Decision record at the end of `docs/plan.md`.
- [ ] Changes to plan written down with reasons. `docs/plan.md`, section "Changes to plan".
- [ ] Contained change: new code only in `cvat/apps/test/` and `cvat-ui/src/components/annotation-counts-page/`; existing files touched: `cvat/settings/base.py`, `cvat/urls.py`, `cvat/asgi.py`, `cvat/schema.yml` (regenerated), `cvat-ui/src/components/cvat-app.tsx`, `cvat-ui/src/components/tasks-page/actions-menu-items.tsx`. Check: `git diff --stat origin/develop...dev-test01`.
- [ ] Recording under 5 minutes. `<<FILL: Loom link and length>>`

## Not finished and why

`<<FILL AT THE END: anything still open. Known gaps, keep the ones that are still true:>>`

- Annotations in overlapping job segments are counted once per job (image tasks use overlap 0; video tasks do not).
- Live updates do not work under the webpack dev server (`yarn start`): its proxy is not configured for WebSockets. The Docker stack is the supported setup.
- Every open socket re-runs the count query on each change; many viewers of one busy task would multiply the load (see decision record).
- No automated UI test for the page or for the reconnect logic; both are checked by hand (lines above).
