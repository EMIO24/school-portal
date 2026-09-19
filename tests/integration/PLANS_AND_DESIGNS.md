# School plans, colours and five portal designs

Open **Superadmin > Portal designs**, or http://localhost:3001/superadmin/appearance . Sign in using your platform owner account.

1. Select a school. Suspended schools can still be configured here.
2. Choose Scholar, Campus, Studio, Executive or Heritage. Each has a different navigation/content arrangement. Choosing a layout loads its suggested palette.
3. Set the school's primary, secondary and accent colours. Choose typography, add the school's logo URL and motto. The live preview changes immediately; it does not save automatically.
4. Choose Setup, Basic or Premium. The feature list shows exactly what will be enabled.
5. Click **Save design and activate plan**. Use **Preview school sign-in** to inspect the login design without signing out of the owner panel. Reload existing school tabs to see the new design and menus.

This is a manual owner assignment, so it does not charge a card. Paystack subscription purchases continue to activate the purchased plan after verification. Layout choices are included on every plan and are independent of feature access. Only platform owners can save these changes; read-only platform staff and school administrators cannot.

## Layouts

| Design | Structure |
| --- | --- |
| Scholar | Branded left sidebar, spacious cards and a welcome banner |
| Campus | Full-width school masthead and horizontal navigation |
| Studio | Slim white navigation rail and compact two-column shortcuts |
| Executive | Right-hand navigation with an asymmetric welcome area |
| Heritage | Centred school identity, framed page and classic navigation tabs |

All layouts adapt to phone screens with an expandable menu. Colours apply across the shell, buttons and existing theme variables; primary/accent text adjusts to contrast. School login pages also use the assigned design. Core data, routes, permissions and records remain the same.

## Features that are now enforced

| Feature | Setup (free) | Basic | Premium |
| --- | --- | --- | --- |
| School branding, all five layouts, people and academic calendar | Yes | Yes | Yes |
| Attendance | - | Yes | Yes |
| Scores and report cards | - | Yes | Yes |
| Fees and PDF receipts | - | Yes | Yes |
| Timetable builder | - | Yes | Yes |
| Notification tools | - | Yes | Yes |
| CBT and DOCX question import | - | - | Yes |
| Advanced analytics | - | - | Yes |
| Bulk student/staff import | - | - | Yes |
| Promotion workflows | - | - | Yes |
| Scratch cards | - | - | Yes |

Basic remains NGN 75,000 per 3 months and Premium NGN 150,000 per 3 months unless the owner edits prices. SMS/email provider usage is separate; there is no unlimited messaging allowance or automatic usage wallet.

Changing a plan changes API feature access immediately. Menus refresh when the school page reloads. Visiting a locked page directly shows upgrade guidance, and directly calling its API is rejected. A downgrade does not delete existing records. Subscription checkout, payment verification and retrieval of historical fee receipts remain reachable under their normal permissions.

Renewal dates are still owner-managed: this release gates features by the assigned plan, not by an automatic expiry/grace-period job. Use the existing owner subscription controls to handle expiry. Suspended/unapproved schools do not regain access just because a plan or design was assigned.

## Test checklist

- [ ] As owner, select a school and save a new layout/colour. Reload its school login and dashboard; confirm the changes.
- [ ] Select a second school and choose a different layout. Confirm both retain their own branding, including in different browser tabs.
- [ ] Set Basic. Attendance, results and fees remain available. CBT, analytics, scratch cards, promotion and bulk imports are locked.
- [ ] Set Premium. Reload and confirm those tools become available.
- [ ] Set Setup. People, calendar and subscription controls remain usable; operational features show upgrade guidance.
- [ ] Open a locked page directly; confirm it does not render the editor.
- [ ] Sign in as a school administrator or read-only platform staff member; confirm design assignment is denied.
- [ ] Check each layout at phone width. Open/close the menu and reach a form without sideways page scrolling.
- [ ] Verify a pending payment after changing the plan; only verified payments credit accounts.

The two local QA schools use Premium so the integration test data remains usable. Other schools keep their existing assigned plan. No payment is made by this fixture setup.

Automated checks:

```powershell
python backend/manage.py test tenants fees accounts cbt.test_admin_workflows --settings=config.settings.test
npm --prefix frontend test -- --watchAll=false --runInBand --runTestsByPath src/__tests__/pages/PortalDesigns.test.js
```
