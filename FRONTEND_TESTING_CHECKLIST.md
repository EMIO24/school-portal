# Manual QA Testing Checklist for School Portal Frontend

**Document Version:** 1.0  
**Last Updated:** 2024  
**Scope:** Frontend UI/UX testing across all user roles and features

---

## Table of Contents

1. [Pre-Testing Setup](#pre-testing-setup)
2. [Common Features (All Roles)](#common-features-all-roles)
3. [Admin Portal Testing](#admin-portal-testing)
4. [Teacher Portal Testing](#teacher-portal-testing)
5. [Student Portal Testing](#student-portal-testing)
6. [Parent Portal Testing](#parent-portal-testing)
7. [Responsive Design Testing](#responsive-design-testing)
8. [Browser Compatibility](#browser-compatibility)
9. [Performance Testing](#performance-testing)
10. [Accessibility Testing](#accessibility-testing)
11. [Bug Reporting Template](#bug-reporting-template)

---

## Pre-Testing Setup

### Prerequisites
- [ ] Backend API running (`docker compose up`)
- [ ] Frontend running (`cd frontend && npm start`)
- [ ] Test data loaded (run migration scripts if needed)
- [ ] Test accounts created for each role
- [ ] Browser cache cleared
- [ ] Browser DevTools open (F12)

### Test Credentials

| Role | Email | Password | Notes |
|------|-------|----------|-------|
| Admin | `admin@testschool.ng` | `AdminStr0ng#1` | Full system access |
| Teacher | `teacher@testschool.ng` | `TeachPass123#` | Class and grade access |
| Student | `student@testschool.ng` | `StudentPass123#` | Limited to own data |
| Parent | `parent@testschool.ng` | `ParentPass123#` | Child's data only |

### Smoke Test (Run First)
- [ ] Frontend loads without console errors
- [ ] Login page displays correctly
- [ ] Admin can login successfully
- [ ] Dashboard loads for logged-in user
- [ ] Logout works and redirects to login

---

## Common Features (All Roles)

### Authentication

#### Login Page
- [ ] Page loads with school branding (logo, name, motto)
- [ ] Email field accepts valid email format
- [ ] Password field masks input
- [ ] "Show password" toggle works
- [ ] Submit button is labeled "Login"
- [ ] Form validation shows error messages:
  - [ ] "Email is required" if empty
  - [ ] "Enter a valid email" if invalid format
  - [ ] "Password is required" if empty
- [ ] After failed login, error message displays
- [ ] Error message disappears when user starts typing
- [ ] Email field has autofocus on page load
- [ ] Form submits on Enter key press
- [ ] Submit button shows loading state (spinner/disabled)
- [ ] After successful login, redirects to appropriate dashboard

#### Session Persistence
- [ ] User stays logged in after page refresh
- [ ] User stays logged in after tab switch (within same session)
- [ ] User's session expires after inactivity timeout
- [ ] Expired session redirects to login automatically
- [ ] Refresh token silently obtains new access token
- [ ] Concurrent requests don't trigger multiple refreshes

#### Logout
- [ ] Logout button is visible in navigation
- [ ] Clicking logout clears session
- [ ] Redirects to login page after logout
- [ ] Back button doesn't return to previous session
- [ ] Tokens cleared from storage

### Navigation

#### Header/Navigation Bar
- [ ] Logo is clickable and returns to dashboard
- [ ] Navigation menu items are visible
- [ ] Active page is highlighted
- [ ] User profile section shows name and avatar (if photo)
- [ ] Hamburger menu works on mobile

#### Sidebar/Main Menu (if applicable)
- [ ] All menu items for user's role are visible
- [ ] Menu items are clickable and navigate correctly
- [ ] Current page is highlighted
- [ ] Menu can be collapsed/expanded (if applicable)

### Error Handling

#### API Errors
- [ ] HTTP 401 (Unauthorized) → Redirect to login
- [ ] HTTP 403 (Forbidden) → Show error message
- [ ] HTTP 404 (Not Found) → Show user-friendly error
- [ ] HTTP 500 (Server Error) → Show error message with retry option
- [ ] Network error → Show message and retry option
- [ ] Timeout error → Show message and retry option

#### Form Errors
- [ ] Required field errors show clearly
- [ ] Field-level errors are highlighted
- [ ] Submit button disabled until errors fixed
- [ ] Error messages are clear and actionable

#### No Data Scenarios
- [ ] Empty lists show appropriate message (e.g., "No students found")
- [ ] Loading state displays while fetching data
- [ ] Pagination works for large datasets

### Notifications/Alerts

#### Toast Notifications
- [ ] Success messages display for completed actions
- [ ] Error messages display for failed actions
- [ ] Warning messages appear for important actions
- [ ] Toasts auto-dismiss after 3-5 seconds
- [ ] Toasts can be manually dismissed
- [ ] Multiple toasts stack without overlapping

#### Modals/Dialogs
- [ ] Modal displays centered on screen
- [ ] Modal has clear title and message
- [ ] Confirm/Cancel buttons are visible
- [ ] Clicking outside modal closes it (if applicable)
- [ ] Escape key closes modal

---

## Admin Portal Testing

### Admin Dashboard

#### Page Load
- [ ] Page loads without errors
- [ ] Welcome message displays with admin name
- [ ] School name displays correctly
- [ ] All main sections are visible

#### Dashboard Sections
- [ ] Quick stats display (# of students, staff, classes)
- [ ] Stats are accurate and current
- [ ] Recent activities section shows latest events
- [ ] Quick action buttons are visible and working:
  - [ ] Add Student
  - [ ] Add Staff
  - [ ] Create Class
  - [ ] Other relevant actions

#### Navigation Menu
- [ ] All sections accessible:
  - [ ] Staff Management
  - [ ] Students
  - [ ] Academics
  - [ ] Enrollment
  - [ ] Attendance
  - [ ] Gradebook
  - [ ] Results
  - [ ] Fees
  - [ ] Timetable
  - [ ] Exams (CBT)
  - [ ] Notifications
  - [ ] Analytics
  - [ ] Promotion

### Staff Management

#### Staff List
- [ ] Page loads with list of all staff
- [ ] Can search/filter by name, role, status
- [ ] Pagination works for large lists
- [ ] Staff details display: name, role, email, phone, address
- [ ] Status indicators show (active/inactive)

#### Add/Edit Staff
- [ ] Add button opens form modal/page
- [ ] Form has all required fields:
  - [ ] First Name
  - [ ] Last Name
  - [ ] Email
  - [ ] Phone
  - [ ] Role (Teacher, Admin, etc.)
  - [ ] Subject (if teacher)
- [ ] Email validation prevents duplicates
- [ ] Phone validation accepts international formats
- [ ] Save button submits form
- [ ] Success message shows after save
- [ ] Can edit existing staff
- [ ] Can deactivate staff (soft delete)
- [ ] Can delete staff (with confirmation)
- [ ] Upload staff photo/avatar
- [ ] View staff profile with full details

#### Bulk Import
- [ ] Can upload CSV file
- [ ] Accepts correct format (headers: name, email, role, etc.)
- [ ] Shows preview of data before import
- [ ] Displays validation errors for invalid rows
- [ ] Allows fixing errors and retrying
- [ ] Successfully imports valid rows
- [ ] Shows success count and any skipped rows

### Students Management

#### Student List
- [ ] Page loads with list of students
- [ ] Can filter by:
  - [ ] Class/Arm
  - [ ] Status (active/graduated)
  - [ ] Gender
  - [ ] Admission year
- [ ] Can search by name, admission number
- [ ] Pagination works correctly
- [ ] Student details display: name, admission #, class, status

#### Add/Edit Student
- [ ] Add button opens form
- [ ] Form has required fields:
  - [ ] First Name
  - [ ] Last Name
  - [ ] Date of Birth
  - [ ] Gender
  - [ ] Email
  - [ ] Admission Number
  - [ ] Class/Arm
  - [ ] Guardian info
- [ ] Can upload student photo
- [ ] Date picker works correctly
- [ ] Can assign multiple guardians
- [ ] Save creates/updates student
- [ ] Success message displays

#### Student Profile
- [ ] Shows all student information
- [ ] Academic history displays (classes by year)
- [ ] Performance summary shows
- [ ] Attendance history visible
- [ ] Fee payment history visible
- [ ] Related guardians displayed
- [ ] Edit and Delete buttons available

#### Bulk Import
- [ ] Similar to staff bulk import
- [ ] Correctly parses student data
- [ ] Handles class assignment
- [ ] Prevents duplicate admission numbers

### Academics Management

#### Sessions & Terms
- [ ] Can create academic session (e.g., "2023/2024")
- [ ] Can create terms within session (e.g., "1st Term")
- [ ] Can set date ranges for terms
- [ ] Can mark term as current
- [ ] Can activate/deactivate terms
- [ ] Cannot delete terms with data attached

#### Classes & Arms
- [ ] Can create class (e.g., "JSS 1")
- [ ] Can create arms within class (e.g., "JSS 1A", "JSS 1B")
- [ ] Can set class level
- [ ] Can assign form tutor to class
- [ ] Can view students in class

#### Subjects
- [ ] Can create subjects
- [ ] Can assign subjects to classes
- [ ] Can assign teachers to subjects
- [ ] Can set subject code
- [ ] Can mark as optional/compulsory
- [ ] Can specify credit hours

#### Calendar & Holidays
- [ ] Can create calendar events
- [ ] Can mark holidays
- [ ] Can set exam dates
- [ ] Can view calendar overview
- [ ] Holidays display on student calendars

### Enrollment

#### Subject Assignment
- [ ] Can assign teachers to subjects
- [ ] Can assign subjects to student arms
- [ ] Shows conflict warnings (e.g., teacher teaching same class twice)
- [ ] Can view assignments by class, teacher, subject

### Attendance

#### Mark Attendance
- [ ] Attendance page shows class list
- [ ] Can select attendance date
- [ ] Can mark present/absent/late
- [ ] Can add remarks
- [ ] Submit stores attendance
- [ ] Cannot mark attendance for future dates
- [ ] Can edit past attendance (if allowed)

#### Attendance Report
- [ ] Can view attendance by class
- [ ] Can view attendance by student
- [ ] Can filter by date range
- [ ] Shows attendance percentage
- [ ] Export to PDF works
- [ ] Export to Excel works

### Gradebook

#### Enter Grades
- [ ] Can select class and subject
- [ ] Can select assessment (test 1, test 2, exam, etc.)
- [ ] Shows list of students
- [ ] Can enter grades in cells
- [ ] Input validation (prevents invalid grades)
- [ ] Can submit grades
- [ ] Can edit submitted grades (if allowed)
- [ ] Success message after save

#### View Grades
- [ ] Can view grades by class/subject/term
- [ ] Shows grade distribution
- [ ] Can view student's grade transcript
- [ ] Calculates GPA correctly

### Results

#### Publish Results
- [ ] Can select term/class for result publishing
- [ ] Shows preview of results before publishing
- [ ] Can publish results for selected term
- [ ] Students can then view results
- [ ] Can unpublish results

#### Result Analysis
- [ ] Can view class average per subject
- [ ] Can view top performing students
- [ ] Can view students below average
- [ ] Export report to PDF

### Fees

#### Fee Categories
- [ ] Can create fee categories (tuition, uniform, etc.)
- [ ] Can set amounts
- [ ] Can mark as mandatory/optional

#### Fee Assignment
- [ ] Can assign fees to classes
- [ ] Can set payment timeline
- [ ] Can mark fees as paid/outstanding

#### Fee Collection
- [ ] Shows outstanding fees by student
- [ ] Shows payment status
- [ ] Can record manual payments
- [ ] Can generate receipts
- [ ] Export fee report

### Timetable

#### Build Timetable
- [ ] Can add periods to timetable
- [ ] Can add classes to periods
- [ ] Can assign teachers to periods
- [ ] Prevents conflicts:
  - [ ] Same teacher teaching 2 classes
  - [ ] Same class with 2 teachers
  - [ ] Same subject twice same day
- [ ] Can delete timetable entries
- [ ] Can view timetable overview

#### Timetable Views
- [ ] Can view timetable by class
- [ ] Can view timetable by teacher
- [ ] Can export to PDF

### Exams (CBT)

#### Exam Management
- [ ] Can create exam with:
  - [ ] Title
  - [ ] Subject
  - [ ] Class
  - [ ] Date/Time
  - [ ] Duration
  - [ ] Total score
- [ ] Can edit exam details
- [ ] Can set as "coming" or "active" or "completed"
- [ ] Can delete exam (if no student attempts)

#### Question Bank
- [ ] Can add questions with:
  - [ ] Multiple choice options
  - [ ] Correct answer
  - [ ] Mark value
- [ ] Can edit questions
- [ ] Can delete questions
- [ ] Can assign questions to exam
- [ ] Can shuffle questions for display

#### Exam Results
- [ ] Can view exam statistics
- [ ] Can view individual student scores
- [ ] Can see student answers vs correct answers
- [ ] Can export results report

### Notifications

#### Create Notifications
- [ ] Can create SMS templates
- [ ] Can create Email templates
- [ ] Can send to specific groups:
  - [ ] All staff
  - [ ] All students
  - [ ] Specific class
  - [ ] Specific student/guardian
- [ ] Can preview message
- [ ] Sending shows progress
- [ ] Shows delivery status

#### Notification History
- [ ] Can view sent notifications
- [ ] Can see delivery status
- [ ] Can resend notifications

### Analytics & Reports

#### Dashboard Charts
- [ ] Shows student enrollment trends
- [ ] Shows fee collection progress
- [ ] Shows attendance trends
- [ ] Shows performance by subject

#### Generate Reports
- [ ] Can generate custom reports
- [ ] Can filter by date range, class, etc.
- [ ] Export to PDF
- [ ] Export to Excel

### Settings (if admin section)

#### School Info
- [ ] Can edit school name
- [ ] Can edit school logo
- [ ] Can edit school address
- [ ] Can edit school motto

#### User Management
- [ ] Can create admin accounts
- [ ] Can view all users
- [ ] Can deactivate users
- [ ] Can reset user passwords

---

## Teacher Portal Testing

### Teacher Dashboard

#### Page Load
- [ ] Page displays correctly
- [ ] Shows teacher name
- [ ] Shows assigned classes
- [ ] Shows recent activities

#### Assigned Classes
- [ ] Shows list of all assigned classes
- [ ] Shows student count per class
- [ ] Can click to view class details

### Grade Entry

#### Interface
- [ ] Can select class and subject
- [ ] Can select assessment type
- [ ] Shows list of students in class
- [ ] Grade input cells are editable
- [ ] Input validation prevents invalid grades

#### Grade Entry Process
- [ ] Can enter grades for single assessment
- [ ] Grades persist after save
- [ ] Can view previously entered grades
- [ ] Can edit grades (if allowed)
- [ ] Cannot modify finalized grades
- [ ] Success message after save

#### Grade Review
- [ ] Can view grades entered
- [ ] Can export grades to file
- [ ] Shows grade statistics

### Attendance

#### Mark Attendance
- [ ] Can select class to mark attendance
- [ ] Can select date (not future dates)
- [ ] Shows all students in class
- [ ] Can mark present/absent/late
- [ ] Can add remarks (e.g., "sick leave")
- [ ] Submit button saves attendance
- [ ] Success message displays

#### Edit Attendance
- [ ] Can modify past attendance (if allowed)
- [ ] Can add remarks to existing entries
- [ ] Shows warning before overwriting

#### Attendance Report
- [ ] Can view attendance summary by student
- [ ] Shows attendance percentage
- [ ] Shows present/absent/late count

### Timetable

#### View Timetable
- [ ] Shows teacher's complete timetable
- [ ] Shows day, period, class, subject
- [ ] Clear time slots
- [ ] Shows current period highlight

### Personal Profile

#### Profile Info
- [ ] Can view own profile
- [ ] Shows name, email, phone
- [ ] Shows subjects taught
- [ ] Shows classes assigned

#### Change Password
- [ ] Can access password change form
- [ ] Requires current password
- [ ] New password validation works:
  - [ ] Min 8 characters
  - [ ] Contains uppercase and lowercase
  - [ ] Contains numbers
- [ ] Confirm password must match
- [ ] Password change succeeds
- [ ] Success message displays

---

## Student Portal Testing

### Student Dashboard

#### Page Load
- [ ] Dashboard displays correctly
- [ ] Shows student name and class
- [ ] Shows key information:
  - [ ] Attendance percentage
  - [ ] Fee status
  - [ ] Recent grades
  - [ ] Next exam/class

#### Quick Access Cards
- [ ] My Results card shows recent grades
- [ ] My Attendance card shows percentage
- [ ] My Fees card shows status
- [ ] My Exams card shows available exams

### Results

#### View Results
- [ ] Can select term to view results
- [ ] Shows all subjects for that term
- [ ] Displays grade, marks, percentage
- [ ] Shows class average for comparison
- [ ] Shows ranking (if enabled)
- [ ] Result publication status clear

#### Result Analysis
- [ ] Can see performance trend (by term)
- [ ] Can compare own grades to class average
- [ ] Can identify weak subjects

### Attendance

#### View Attendance
- [ ] Can view attendance by month/term
- [ ] Shows present/absent/late count
- [ ] Shows percentage
- [ ] Shows trend graph
- [ ] Can view detailed attendance dates

### Fees

#### Fee Status
- [ ] Can view all fees
- [ ] Shows paid/outstanding amounts
- [ ] Shows payment due dates
- [ ] Shows payment history
- [ ] Shows receipts (if generated)

#### Make Payment (if implemented)
- [ ] Can initiate payment
- [ ] Can select payment method
- [ ] Payment gateway integration works
- [ ] Confirmation after payment
- [ ] Receipt available

### Exams (CBT)

#### Exam List
- [ ] Shows available exams
- [ ] Shows exam status (coming, active, completed, expired)
- [ ] Shows exam date/time
- [ ] Shows exam duration
- [ ] Shows total marks

#### Take Exam
- [ ] Can start exam at scheduled time only
- [ ] Exam page loads correctly
- [ ] Questions display clearly
- [ ] Can select multiple choice answer
- [ ] Can navigate between questions
- [ ] Timer shows remaining time
- [ ] Warning at 5 min remaining
- [ ] Can save answers periodically
- [ ] Auto-save works if connection lost
- [ ] Cannot submit after time expires
- [ ] Submit button confirms submission

#### Exam Review
- [ ] Can view submitted exam
- [ ] Shows questions and own answers
- [ ] Shows correct answers (if allowed)
- [ ] Shows score (if released)

### Timetable

#### View Timetable
- [ ] Shows class timetable
- [ ] Shows subjects and teachers
- [ ] Clear formatting
- [ ] Highlights current period (if applicable)

### Personal Profile

#### Profile Info
- [ ] Can view own profile
- [ ] Shows name, class, admission number
- [ ] Shows guardian information
- [ ] Shows contact information (if applicable)

#### Change Password
- [ ] Can change password
- [ ] Password validation same as teacher

---

## Parent Portal Testing

### Parent Dashboard

#### Page Load
- [ ] Dashboard displays correctly
- [ ] Shows parent name
- [ ] Shows linked children

#### Child Selection
- [ ] Can select which child to view
- [ ] Dashboard updates when child selected
- [ ] Can see all linked children

#### Child Information
- [ ] Shows child's name and class
- [ ] Shows recent grades
- [ ] Shows attendance summary
- [ ] Shows fee status
- [ ] Shows upcoming exams

### Child's Results

#### View Results
- [ ] Can select term
- [ ] Shows all subjects and grades
- [ ] Shows class average for comparison
- [ ] Can download/print results

#### Performance Tracking
- [ ] Can view performance trend
- [ ] Can see improvement/decline
- [ ] Can identify strong/weak subjects

### Child's Attendance

#### View Attendance
- [ ] Shows attendance percentage
- [ ] Shows attendance by date
- [ ] Shows absence patterns
- [ ] Shows notes/reasons (if provided)

### Fees & Payments

#### Fee Status
- [ ] Shows all fees
- [ ] Shows paid amounts
- [ ] Shows outstanding amounts
- [ ] Shows payment due dates

#### Payment History
- [ ] Shows all payments made
- [ ] Shows dates and amounts
- [ ] Shows payment methods
- [ ] Can download receipts

#### Make Payment (if implemented)
- [ ] Can initiate payment online
- [ ] Payment gateway works
- [ ] Confirmation and receipt provided

### Child's Timetable

#### View Timetable
- [ ] Shows child's class timetable
- [ ] Clear formatting
- [ ] Shows subject and teacher info

### Notifications

#### Receive Notifications
- [ ] Receives school notifications
- [ ] Shows unread count
- [ ] Can mark as read
- [ ] Can delete notifications
- [ ] Push notifications work (if enabled)

### Personal Profile

#### Profile Info
- [ ] Can view own profile
- [ ] Shows contact information
- [ ] Can update phone/email

#### Change Password
- [ ] Can change password
- [ ] Same validation as others

---

## Responsive Design Testing

### Mobile Testing (iPhone, Android)

#### Viewport Sizes to Test
- [ ] 375px (iPhone SE)
- [ ] 390px (iPhone 12)
- [ ] 430px (iPhone 15 Plus)
- [ ] 480px (Android small)
- [ ] 540px (Android standard)

#### Mobile Specific Tests
- [ ] Navigation collapses to hamburger menu
- [ ] Content is readable (no horizontal scroll)
- [ ] Form fields are touch-friendly (min 44px height)
- [ ] Buttons are clickable without adjacent overlap
- [ ] Images scale correctly
- [ ] Modals display full screen or centered
- [ ] Tables have horizontal scroll or rearrange
- [ ] Date pickers work on mobile
- [ ] Dropdown menus display correctly

### Tablet Testing

#### Viewport Sizes to Test
- [ ] 600px (Small tablet)
- [ ] 768px (iPad)
- [ ] 1024px (iPad Pro)

#### Tablet Specific Tests
- [ ] Layout utilizes available space
- [ ] Navigation adapts appropriately
- [ ] Sidebar may appear or hide
- [ ] Multi-column layouts work
- [ ] Images and content scale properly

### Desktop Testing

#### Viewport Sizes to Test
- [ ] 1280px (Older desktop)
- [ ] 1440px (Standard desktop)
- [ ] 1920px (Full HD)
- [ ] 2560px (Ultra-wide)

#### Desktop Specific Tests
- [ ] Multi-column layouts display
- [ ] Sidebars visible
- [ ] Content doesn't overflow
- [ ] Hover states work
- [ ] Tooltips display correctly

### Orientation Tests
- [ ] Portrait mode layouts correct
- [ ] Landscape mode layouts correct
- [ ] Rotation doesn't break layout
- [ ] Content reflows appropriately

---

## Browser Compatibility

### Desktop Browsers

#### Chrome/Chromium
- [ ] Latest version
- [ ] -2 version
- [ ] Edge (latest)
- [ ] Opera (latest)

#### Firefox
- [ ] Latest version
- [ ] -1 version

#### Safari
- [ ] Latest macOS version
- [ ] -1 version

#### Internet Explorer (if required)
- [ ] IE 11 (if supported)
- [ ] Note: Most modern apps drop IE11 support

### Mobile Browsers

#### iOS
- [ ] Safari iOS (latest)
- [ ] Chrome iOS (latest)

#### Android
- [ ] Chrome Android (latest)
- [ ] Firefox Android (latest)
- [ ] Samsung Internet (latest)

### Browser-Specific Tests

#### All Browsers
- [ ] Page loads without errors
- [ ] No console errors
- [ ] No console warnings
- [ ] All features work
- [ ] Forms submit correctly
- [ ] File uploads work
- [ ] Date pickers function
- [ ] Modals display correctly

#### CSS Rendering
- [ ] Fonts display correctly
- [ ] Colors render accurately
- [ ] Spacing/padding correct
- [ ] Borders display properly
- [ ] Shadows render (if used)
- [ ] Animations smooth (if used)

#### JavaScript Execution
- [ ] No syntax errors
- [ ] Event handlers work
- [ ] Timers/intervals function
- [ ] Promises resolve correctly
- [ ] Async/await works

---

## Performance Testing

### Page Load Testing

#### Metrics to Measure
- [ ] First Contentful Paint (FCP) < 1.5s
- [ ] Largest Contentful Paint (LCP) < 2.5s
- [ ] Cumulative Layout Shift (CLS) < 0.1
- [ ] Total page size
- [ ] Number of requests
- [ ] Time to interactive

#### Tools
- [ ] Chrome DevTools (Lighthouse)
- [ ] WebPageTest
- [ ] Google PageSpeed Insights

### Runtime Performance

#### Scrolling Performance
- [ ] Scrolling is smooth (60 FPS)
- [ ] No jank or stuttering
- [ ] Works with large lists

#### Form Submission
- [ ] Form submits within reasonable time
- [ ] Loading state displays
- [ ] No multiple submissions with double-click

#### Data Loading
- [ ] Tables with pagination load quickly
- [ ] Lazy loading works (if implemented)
- [ ] Infinite scroll works (if implemented)

### Memory Usage
- [ ] No memory leaks (DevTools Memory tab)
- [ ] Memory usage stays stable
- [ ] Browser doesn't crash with large datasets

### Network Usage
- [ ] Unnecessary requests eliminated
- [ ] API responses optimized
- [ ] Images optimized/compressed
- [ ] CSS/JS minified in production
- [ ] Caching headers set correctly

---

## Accessibility Testing

### Keyboard Navigation
- [ ] Can navigate entire site with Tab key
- [ ] Logical tab order
- [ ] Can activate buttons with Enter
- [ ] Can select checkboxes with Space
- [ ] Can navigate menus with arrow keys
- [ ] Can close modals with Escape

### Screen Reader Testing

#### Use NVDA (Windows) or VoiceOver (Mac)
- [ ] All text is readable
- [ ] Form labels associated with inputs
- [ ] Buttons have descriptive labels
- [ ] Images have alt text
- [ ] Links have descriptive text
- [ ] Table headers associated with cells
- [ ] Lists are structured properly

### Visual Accessibility

#### Color Contrast
- [ ] Text contrast ratio ≥ 4.5:1 for normal text
- [ ] Text contrast ratio ≥ 3:1 for large text
- [ ] Don't rely on color alone (use icons/patterns)

#### Font Size
- [ ] Minimum 14px for body text
- [ ] Adequate line height (1.5x)
- [ ] Adequate letter spacing

#### Focus Indicators
- [ ] Interactive elements have visible focus
- [ ] Focus outline at least 2px
- [ ] Focus color contrasts with background

### Form Accessibility
- [ ] Labels associated with inputs
- [ ] Error messages linked to fields
- [ ] Required fields marked
- [ ] Instructions clear
- [ ] Form can be submitted keyboard-only
- [ ] Date pickers accessible

### Mobile Accessibility
- [ ] Touch targets at least 44x44px
- [ ] Touchable elements spaced properly
- [ ] No hover-only information
- [ ] Gestures have keyboard alternatives

---

## Bug Reporting Template

When you find a bug, create an issue with the following information:

### Bug Report

**Title:** [Brief description of bug]

**Severity:** 
- [ ] Critical (app crashes, data loss, security)
- [ ] High (major feature broken)
- [ ] Medium (feature doesn't work as expected)
- [ ] Low (minor issue, workaround available)

**Environment:**
- Browser: [Chrome/Firefox/Safari/etc.]
- OS: [Windows/Mac/iOS/Android]
- Device: [Desktop/Tablet/Mobile]
- Resolution: [e.g., 1920x1080]
- Network: [LAN/WiFi/Mobile]

**Steps to Reproduce:**
1. Login as [role]
2. Navigate to [page]
3. [Action]
4. [Expected result vs actual result]

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Screenshots/Videos:**
[Attach if possible]

**Console Errors:**
[Any errors in DevTools console]

**Additional Context:**
[Any other relevant information]

---

## Test Execution Log

| Date | Tester | Test Area | Result | Notes |
|------|--------|-----------|--------|-------|
| | | | PASS/FAIL | |
| | | | PASS/FAIL | |
| | | | PASS/FAIL | |

---

## Sign-Off

| Role | Name | Date | Status |
|------|------|------|--------|
| QA Lead | | | ☐ Approved |
| Dev Lead | | | ☐ Approved |
| Product Manager | | | ☐ Approved |

---

## Appendix: Useful DevTools Techniques

### Browser DevTools Inspection

#### Network Tab
1. Open DevTools → Network tab
2. Perform action
3. Check:
   - Request URL
   - Response status (200, 401, 404, 500)
   - Response time
   - Request/Response headers
   - Response body (JSON structure)

#### Console Tab
1. Open DevTools → Console tab
2. Check for:
   - Errors (red X)
   - Warnings (yellow triangle)
   - Log messages
   - Unhandled promise rejections

#### Application Tab (Storage)
1. Open DevTools → Application tab
2. Check:
   - Local Storage (tokens, user settings)
   - Session Storage
   - Cookies
   - Service Workers (if applicable)

#### Performance Tab
1. Open DevTools → Performance tab
2. Record user actions
3. Check:
   - Flame chart for bottlenecks
   - Frame rate
   - Memory usage
   - CPU usage

#### Accessibility Tab
1. Open DevTools → Accessibility tab
2. Check:
   - ARIA attributes
   - Heading hierarchy
   - Focus order
   - Contrast issues

---

## Testing Tools & Extensions

### Recommended Browser Extensions
- **Accessibility Checker** - WAVE
- **Contrast Checker** - Color Contrast Analyzer
- **Performance** - Lighthouse
- **Screen Reader** - NVDA / VoiceOver
- **API Testing** - Postman
- **Mobile Emulation** - Chrome DevTools

### Online Testing Platforms
- BrowserStack (for real device testing)
- LambdaTest
- Sauce Labs
- GTmetrix (performance)
- WebAIM (accessibility)

---

**End of Manual QA Testing Checklist**
