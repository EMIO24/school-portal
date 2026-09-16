# School Portal User Guide

Read the guide from **User guide** in the portal menu or `/help` before signing in. **PDF downloads are available only in Superadmin > User guide**.

## Getting started

Start here if you are using the portal for the first time.

### Sign in to the correct school

1. Use the school login link supplied by your school. Schools share the platform but have separate accounts and records.
2. Enter your own email and password. A platform owner uses the separate platform login page.
3. If you are asked to change a temporary password, complete that step before continuing. Do not share accounts.

### Find your way around

1. On a phone or tablet, tap Explore portal to open the menu. Tap a destination to open its page.
2. Tap Close menu or the shaded area outside the menu to close it. Keyboard users can press Escape.
3. Scholar, Campus, Studio, Executive and Heritage arrange navigation differently on larger screens. They use the same page names and school records.
4. Open User guide in the menu whenever you need help. Choose your role below. Downloadable copies are managed from Superadmin > User guide.

### Save, search and download

1. Complete required fields before selecting Save or Submit. Wait for a success message before leaving the page.
2. Use school year, term, class and subject filters when available. An empty list may mean the selected filter has no records.
3. On a narrow screen, swipe inside a wide table or timetable to see its remaining columns. The whole page should not need sideways scrolling.
4. Downloaded PDF receipts and reports normally appear in your device Downloads folder. Allow downloads if your browser asks.

### Understand plans

1. Setup gives the school access to people, academic setup and subscription controls.
2. Basic enables attendance, scores/results, fees, timetables and notification tools.
3. Premium also enables CBT, DOCX questions, advanced analytics, bulk imports, promotion and scratch cards.
4. A missing tool may be excluded by your school plan or your account role. Ask your school administrator; changing the web address does not grant access.
5. SMS and other provider usage are separate from the subscription. Renewal dates are currently managed by the platform owner.

## Superadmin / platform owner

Manage schools and platform access from the owner panel. These accounts are separate from school administrators.

### Sign in with two-factor authentication

1. Open the platform login page and enter your owner email and password.
2. For first-time setup, scan the QR code using an authenticator app, or enter its setup key in that app. Enter the current six-digit authenticator code into the portal.
3. Save the recovery codes privately when shown. Never share the setup key, password or recovery codes with school users.
4. If a code is rejected, enable automatic time on your phone, wait for a fresh code and retry. Use the most recently configured authenticator entry.
5. Read-only platform staff can inspect permitted records but cannot activate schools, change payment settings or assign designs.

### Review and activate a school

1. Open Schools and filter for pending registrations. Select Manage for the school.
2. Check the school identity and contact details before choosing Approve. Reject a registration if it should not be activated.
3. Use Create a school when onboarding a school yourself. Supply its own school administrator account.
4. In school management, add or enable the appropriate administrator. Send temporary credentials privately.
5. Suspend blocks school access while retaining records. Activate restores an approved school. A plan payment or design assignment does not undo suspension.

### Assign a design and plan

1. Open Portal designs and choose the school.
2. Choose Scholar, Campus, Studio, Executive or Heritage. Selecting a design loads its suggested colours.
3. Set primary, secondary and accent colours, typography, logo URL and motto. Review the sample preview.
4. Choose Setup, Basic or Premium and read the included feature list.
5. Select Save design and activate plan. This is a manual activation and does not charge the school.
6. Use Preview school sign-in to inspect its login page while keeping your owner session. School users should reload their pages to see new branding and menus.

### Manage payments and subscriptions

1. Open Payments to view prices, settlement accounts and recent payment orders.
2. Set the price, number of months and availability for Basic and Premium. New checkouts use the new settings; pending orders retain their original price.
3. Create and verify each school beneficiary in Paystack, then connect that school subaccount code in Payments. Check the displayed beneficiary and bank suffix carefully.
4. School fee money goes to the connected school account, less provider charges. Subscription money goes to the platform account.
5. Use Verify with Paystack to recheck a recent order. An order requiring review must be reconciled before credit or refund decisions; do not mark it successful without verification.
6. Paystack keys and public webhook setup are deployment tasks. Keep secret keys out of frontend files and user messages. Test mode and live mode use separate configurations.

### Manage platform staff and activity

1. Open Platform staff and activity. Give each platform colleague a separate account.
2. Choose owner access only for people authorised to make platform changes. Use read-only access for reviewers.
3. Disable an account when access is no longer needed. Do not reuse another person's account.
4. Review activity records when investigating school, account, plan or payment changes.
5. Arrange regular backups and restoration checks with the deployment administrator. The owner panel does not replace a tested recovery procedure.

## School administrator

Set up your school and manage its daily operations. You can work only within your own school.

### Prepare a school for use

1. Open Calendar and create the academic session and terms. Check the current session and current term.
2. Create the class levels, class arms and subjects needed by your school.
3. Add staff accounts and assign teachers to classes or subjects where applicable.
4. Add students with the correct admission details and current class. Check names and contact details before saving.
5. Make sure parent accounts are linked to the correct students. If a family cannot see a child, investigate the account/link rather than giving them another person's login.

### Manage students and staff

1. Open Students or Staff to search, filter and open a record.
2. Use Add student or Add staff to create an individual record. Supply a unique email where an account is required.
3. The student form generates the admission number when saved; the form identifies it as the student's initial password. Share initial credentials privately and have the student change the password.
4. Office staff who need administration tools must have an authorised school administrator account. A teacher account has teaching permissions.
5. On Premium, use Import students or Import staff for batch entry. Follow the displayed CSV format, review validation errors, correct the source file and retry.
6. The downloadable import guide may be a PDF, but the upload file must still be the format requested by the import screen.

### Attendance, timetable and results

1. Use Attendance to review registers by term, class and date. Teachers record the class attendance they are authorised to manage.
2. Open Timetable, add periods with start/end times, then assign lessons to the correct day, class, teacher and subject. Resolve conflicts before saving.
3. Use Results to manage the selected session, term and class. Check score completeness and remarks before publishing results or downloading reports.
4. Teachers enter scores through their own accounts. Ask them to correct missing or inaccurate entries before publication.

### Collect and record school fees

1. Open Fee setup to create fee categories and schedules for the correct term and class level. Enter the amount and due date where needed.
2. Use Fee collection to review balances. Confirm the student and fee before recording a cash or bank-transfer payment.
3. Record only money actually received. Online Paystack payments are credited by verification, not by entering them as a manual payment.
4. Ask the platform owner to connect your school settlement account before families use Paystack checkout.
5. Use the available PDF receipt/report download controls. If a family has paid but the balance is unchanged, keep the payment reference and request verification.

### CBT and questions on Premium

1. Open Question bank and select the appropriate subject/topic. Create questions manually with their options and correct answers.
2. To import a Word file, use the DOCX upload option and follow the supplied question template. Each recognised question becomes a separate question record.
3. Review the parsed question count, text, options and answers before completing the import. For 40 valid questions, confirm that 40 were recognised and saved.
4. Open Exams to create an exam, set its class/subject, schedule, duration and question-selection rule. Save and review the configuration before making it available.
5. Use Exam results to review submitted attempts. Do not change an active exam without considering students already taking it.

### Notifications and other Premium tools

1. In Notifications, choose the intended recipients and channel, write or select the message, review it and send. Check the history/status afterwards.
2. SMS/email delivery requires configured providers and any required credit. A send request does not guarantee delivery.
3. Use Scratch cards to generate the intended result-access cards and download the PDF. Keep unused PINs private.
4. Use Promotion only after checking the academic period and student destination classes. Review results of the operation.
5. Advanced analytics summarises recorded school data. Select the correct term and use Refresh Analytics; incomplete source data produces incomplete summaries.

### Renew the portal subscription

1. Open Portal subscription to compare available plans, prices and billing periods.
2. Choose a plan and continue to Paystack. Return to the portal after checkout and check the payment status.
3. A verified subscription payment updates the plan and paid-through date. Payments are one-time renewals; the card is not automatically charged.
4. A plan change during an existing paid period may require the platform owner. Ask the owner about renewal dates, suspension, design changes or unavailable features.

## Staff / teachers

Teaching staff use teacher accounts. Administrative staff use school administrator accounts when authorised; there is no separate cashier or generic office-staff role.

### Prepare your account

1. Sign in with your own school account. Change a temporary password when required.
2. Check that the school and your account name are correct.
3. If assigned classes or subjects are missing, ask the school administrator to correct your assignments.

### Take attendance

1. Open Take attendance. Select the correct class, academic period and date.
2. Review the student list and mark the appropriate attendance status for each student.
3. Save or submit the register and check that it was recorded. Review the date before correcting an existing register.

### Enter scores

1. Open Scores and select the correct class, subject and term.
2. Enter assessment and examination scores in the supplied fields. Keep within the configured maximum marks.
3. Review the names and scores before saving. Correct validation errors and check the success message.
4. Use Student development to record supported skills/behavioural assessments where enabled.
5. School administrators manage publication and school-wide result settings.

### Use your timetable

1. Open My timetable to see assigned lessons. Use the available day or period view.
2. On a phone, swipe inside the timetable if all columns are not visible.
3. Report missing lessons or clashes to the school administrator; do not use another teacher's login.

### Know your permissions

1. Teacher accounts do not manage platform billing, school plans or portal designs.
2. If you also need administrative access, the school must authorise the appropriate account role.
3. A missing tool can be caused by the school plan, account role or class/subject assignment. Contact the school administrator with the page name and error message.

## Parent / guardian

View and pay for students linked to your own parent account.

### Open your child's dashboard

1. Use your school login link and sign in to your parent account.
2. Choose the child you want to view when more than one is linked.
3. Check the displayed name and class before opening results or making a payment.
4. If a child is missing or the wrong child appears, stop and contact the school administrator to correct the link.

### Review progress and messages

1. The dashboard shows available result, attendance, fee and timetable information for the selected child.
2. Open the child's results for available report details. Results may not appear until the school publishes them.
3. Use the notification/message control to read messages delivered to your account.
4. Contact the school about incorrect attendance, marks or class assignments. Parents cannot edit those records.

### Pay school fees

1. Open the selected child's Fees page. Select the academic term and unpaid fee items.
2. Check the outstanding amount and choose Pay Online via Paystack. Use the secure Paystack checkout options offered.
3. Return to the portal and wait for verification. If signed out, sign in using the account that started the payment.
4. When payment is verified, download the PDF receipt. Keep the payment reference.
5. If the status is pending or verification is unavailable, use Check again later. Do not pay again simply because the browser closed or the balance has not yet updated.
6. If online payment is unavailable, ask the school whether its settlement account has been connected. Use only payment alternatives the school confirms.

## Student

Use your own school account to view learning information, take available exams and check fees.

### Find your school information

1. Sign in through your school link. Check your name and class.
2. Open Your timetable for lessons and Attendance for recorded attendance.
3. Open Results to view results made available by the school. Download the offered PDF report when available.
4. Premium schools may offer Performance for a more detailed view of your progress. Ask your school if a feature is unavailable.

### Take a computer-based exam

1. Open Exams and check the available exam name, subject, start/end time and duration.
2. Start only when you are ready, have a reliable connection and have read the exam instructions.
3. Answer each question and use the question navigation to review your work. Watch the timer.
4. Avoid leaving the exam tab; the system can record tab changes according to the school's exam rules.
5. Use Submit when finished and check the submission confirmation. Do not repeatedly start new attempts if the connection fails; contact the invigilator and follow the existing attempt's status.
6. Open the available exam result or review after the school permits it.

### View or pay fees

1. Open Fees, select the term and review outstanding items.
2. If you are paying yourself, follow Paystack checkout and return for verification. Otherwise ask your parent/guardian to use their linked account.
3. Save the PDF receipt after verification. Keep the reference if verification is pending and contact the school before paying again.

### Protect your account

1. Keep your password private and sign out on shared devices.
2. Tell the school administrator about an incorrect profile, class, result or payment record.
3. Students cannot change school records, publish results or activate a plan.

## Troubleshooting and support

Use these checks before asking for help.

### Cannot sign in

1. Check the school link and account email. A platform owner signs in at the platform login page.
2. Check for a required temporary-password change or owner authenticator step.
3. If access is disabled or the school is suspended, contact the school administrator or platform owner. Paying again does not undo a suspension.
4. Do not send your password, authenticator key or recovery codes to support.

### A page is empty or a feature is missing

1. Check the term, class, subject and date filters first.
2. Confirm that the school has entered/published the relevant records and assigned your account correctly.
3. Check whether the feature needs Basic or Premium. Only the platform owner or a verified subscription can activate the relevant plan.
4. Reload the page after a plan or design change. On a phone, close the menu to return to the page.

### Payment or download problems

1. Keep the payment reference and check its status before attempting another payment. Only a verified payment produces credit.
2. Look in Downloads for a PDF and allow the browser to download files.
3. For support, provide your school, page name, approximate time, reference where applicable and a description of the problem. Mask sensitive details in screenshots.

### Who to contact

1. Students, parents and teachers: contact your school administrator first.
2. School administrators: contact the platform owner for plans, design assignments, settlement setup or school suspension.
3. Platform staff: contact the platform owner or deployment administrator for two-factor recovery, provider configuration and backups.

