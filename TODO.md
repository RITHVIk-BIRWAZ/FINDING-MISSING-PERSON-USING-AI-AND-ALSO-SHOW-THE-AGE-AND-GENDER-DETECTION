# TODO List for Missing Person App Enhancements

## 1. Add "Lost Lists" to Public Portal Menu
- [x] Update `public_portal()` function to include "Lost Lists" in the sidebar radio options.

## 2. Create `lost_lists_tab()` Function
- [x] Implement new function to fetch all missing persons with status='Missing'.
- [x] Display missing persons in a grid format with images and names.
- [x] Ensure proper formatting and responsiveness.

## 3. Update Menu Handling in `public_portal()`
- [x] Add elif condition for "Lost Lists" to call `lost_lists_tab()`.

## 4. Remove "Track Reports" from Admin Portal Menu
- [x] Update `admin_portal()` function to remove "Track Reports" from sidebar radio options.

## 5. Update "Manage Reports" Phone Display
- [x] Change phone display to full number (remove mask_phone_number) in admin "Manage Reports".

## 6. Add Buttons for "Under Investigation" Status
- [ ] For 'Under Investigation' status in "Manage Reports", add "Mark as Found" and "Delete" buttons in action_cols.

## 7. Remove Notifications for New Public Reports
- [ ] Remove create_notification call in report_missing_person_form() for new reports.

## 8. Modify Sighting Matching and Notifications
- [x] Update search_by_image_tab() to store sighting as report and run matching pipeline.
- [x] Create notifications with full reporter phone for matches.
- [x] Ensure automatic backend matching and admin notifications with sound for matches.

## 9. Testing and Verification
- [ ] Test "Lost Lists" display for proper grid formatting.
- [ ] Test admin "Manage Reports" changes.
- [ ] Test notification modifications.
- [ ] Verify matching pipeline in sightings.
