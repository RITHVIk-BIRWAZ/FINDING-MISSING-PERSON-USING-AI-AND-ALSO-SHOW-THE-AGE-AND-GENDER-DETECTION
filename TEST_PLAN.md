## Comprehensive Test Plan

### 1. Public Portal
- **Happy-path submission**: Fill all required fields, allow browser GPS, upload valid photo, verify success toast + tracking ID.
- **Missing required fields**: Leave name/location/photo blank → expect inline warnings and no DB insert.
- **Invalid phone number**: Enter <7 digits → expect validation error.
- **Consent required**: Uncheck consent checkbox → submission blocked.
- **Manual coordinates**: Deny GPS, type lat/lng manually (valid & invalid formats) → verify acceptance/error.
- **Large image / corrupted image**: Upload >5MB or corrupted bytes → ensure graceful failure.
- **Network retry**: Simulate slow connection (DevTools throttling) to confirm spinner and no duplicate inserts.

### 2. Found Someone / Image Search
- Upload photo and trigger search → confirm spinner and either random match card or “no matches” warning.
- Upload file with no face (landscape) → expect deep learning error message handled.

### 3. Tracking Portal (Admin)
- Accessible only via Admin → Track Reports.
- **Valid tracking ID**: Use ID from submission; verify status, map pin (when coords exist).
- **Invalid ID**: Random string → show informative error.
- **Case without coordinates**: Ensure map widget hidden and explanatory text shown.

### 4. Admin Login & Session
- Wrong credentials → error toast, login state stays False.
- Correct credentials → sidebar unlocks, session persists until logout.
- Logout → session cleared, admin-only data hidden.

### 5. Dashboard
- Metrics update after adding/finding/deleting reports.
- Heatmap only renders with lat/lng; verify no crash when DB empty.
- Toast notifications appear for unread alerts.

### 6. Manage Reports
- Search filter (case-insensitive) and status multi-select.
- Expand report: images render, description shows markdown, contact info is masked.
- Buttons:
  - Mark as Found → status, metrics, and notifications update.
  - Mark Under Investigation → status change persists on refresh.
  - Delete Report → confirmation message, entry removed.
- Map widget hidden when coordinates null.

### 7. Alerts & Matches Center
- Simulate new report (public portal) → unread alert visible; confirm audible alert, browser popup, and vibration (if supported); mark as read to clear badge.
- Run `Find Matches` workflow → ensure queue entry appears with details JSON.
- Actions: Under Review, Escalate (creates notification), Dismiss.

### 8. Automated Matching
- Upload identical photos → confirm facial match recorded, notification generated, statuses switch to “Match Found - Await Review,” Manage view shows warning banner.
- Similar names/locations but different photos → contextual match recorded.
- No faces detected → user-friendly error message, no DB changes.

### 9. Security & Privacy
- Verify phone number masking everywhere except DB/raw logs.
- Ensure public portal rate limits (manual check by rapid submissions or proxy).
- Confirm config credentials not exposed client-side.
- Attempt direct navigation to admin URLs without login → redirected to login form.

### 10. Non-Functional
- **Performance**: Submit 50+ reports and ensure Manage view still responsive.
- **Resilience**: Temporarily lock DB file (simulate busy) → app should show error banner, not crash.
- **Accessibility**: Tab order, focus outlines, alt text on images.

### 11. Regression Automation
Run `pytest tests/test_app_backend.py` on every change to cover:
- Schema creation and migrations.
- Notification lifecycle.
- Matching pipeline + alert generation.

Document results (pass/fail, screenshots) in your QA tracker after each build.

