# Profile and account setup guide

This guide explains how a school administrator creates profiles and login accounts for students, parents and school staff.

Use this after the school has already been created and approved by the platform owner.

## 1. Before creating people

Set up the school basics first:

1. Sign in as the school administrator.
2. Open **Academic Calendar**.
3. Create the current academic session.
4. Create the current term.
5. Open **Classes**.
6. Create class levels, for example `JSS1`, `JSS2`, `SS1`.
7. Create class arms, for example `JSS1 A`, `JSS1 B`.
8. Open **Subjects**.
9. Create the school subjects.

Create people only after classes exist, because students and teachers need to be attached to classes.

## 2. Create a staff account

Use this for teachers, school administrators, bursars and other school workers.

1. Sign in as the school administrator.
2. Go to **Staff**.
3. Click **Add Staff**.
4. Enter the staff member's details:
   - First name
   - Last name
   - Email address
   - Phone number
   - Role
   - Staff ID, if the form allows manual entry
5. Save the staff profile.

The portal creates a login account for the staff member.

Staff login details:

```text
Email: the staff email address
Initial password: the staff ID
```

Example:

```text
Email: teacher@school.com
Staff ID: STF-2026-001
Password: STF-2026-001
```

After first login, the staff member should be sent to **Change Password** and must choose a new private password.

## 3. Create a student account

1. Sign in as the school administrator.
2. Go to **Students**.
3. Click **Add Student**.
4. Enter the student details:
   - First name
   - Last name
   - Email address
   - Gender
   - Date of birth
   - Class
   - Parent or guardian details, if available
5. Save the student profile.

The portal creates a login account for the student.

Student login details:

```text
Email: the student email address
Initial password: the admission number
```

Example:

```text
Email: student@school.com
Admission number: ADM-2026-001
Password: ADM-2026-001
```

After first login, the student should be sent to **Change Password** and must choose a new private password.

## 4. Create or link a parent account

Parents are different because they must be linked to one or more students.

The normal workflow is:

```text
Create student profile → Create or identify parent account → Link parent to student
```

Parent access works only when the parent is linked to the child.

### Option A: Parent uses phone OTP login

Use this when the parent will sign in with a phone number and OTP.

1. Add the parent's phone number while creating or editing the student.
2. Confirm the parent is linked to the student.
3. Tell the parent to open the parent login page.
4. The parent enters their phone number.
5. The portal sends or generates a one-time code.
6. The parent enters the code and signs in.

Parent OTP login details:

```text
Phone number: parent phone number saved on the parent account
Password: not required for OTP login
```

### Option B: Parent uses email and password login

Use this when the parent should sign in with an email and password.

1. Create the parent account with role `parent`.
2. Give the parent an email address.
3. Set or generate an initial password.
4. Link the parent account to the student.
5. Give the parent the login details securely.

Parent email login details:

```text
Email: parent email address
Initial password: the password set for the parent account
```

If the parent has more than one child in the school, link the same parent account to each child. Do not create duplicate parent accounts for the same parent unless they use different contact details.

## 5. Bulk import students or staff

Use bulk import when you have many records.

### Students

1. Go to **Students**.
2. Open **Bulk Import**.
3. Download or follow the student CSV format.
4. Fill the CSV carefully.
5. Upload the CSV.
6. Review any row errors.
7. Fix errors and upload again if needed.

Imported students get accounts.

```text
Student email: from the CSV
Initial password: admission number
```

### Staff

1. Go to **Staff**.
2. Open **Bulk Import**.
3. Download or follow the staff CSV format.
4. Fill the CSV carefully.
5. Upload the CSV.
6. Review any row errors.
7. Fix errors and upload again if needed.

Imported staff get accounts.

```text
Staff email: from the CSV
Initial password: staff ID
```

## 6. What to give each user

Give each user only their own login details.

### Student

```text
School login link:
Email:
Temporary password: admission number
Instruction: sign in and change your password immediately
```

### Staff

```text
School login link:
Email:
Temporary password: staff ID
Instruction: sign in and change your password immediately
```

### Parent using OTP

```text
Parent login link:
Phone number to use:
Instruction: request OTP and enter the code
```

### Parent using email and password

```text
Parent login link:
Email:
Temporary password:
Instruction: sign in and change your password immediately
```

## 7. Safe password rules

Follow these rules when sharing login details:

1. Do not send all user passwords in one public group chat.
2. Give each user only their own temporary password.
3. Ask users to change their password on first login.
4. Do not reuse the same password for all users.
5. If a password is exposed, reset it immediately.
6. Disable accounts for staff who leave the school.
7. Keep parent accounts linked only to their own children.

## 8. Quick test checklist

After creating accounts, test these flows:

1. Student can sign in with email and admission number.
2. Student is asked to change password.
3. Student can see only their own dashboard/results/fees.
4. Staff can sign in with email and staff ID.
5. Staff is asked to change password.
6. Teacher can access only assigned school work.
7. Parent can sign in by OTP or email/password.
8. Parent sees only linked children.
9. A user from another school cannot access this school.

## 9. Troubleshooting

### Student cannot log in

Check:

1. The student has an email address.
2. The student account is active.
3. The student is using the admission number as the temporary password.
4. The student is signing in under the correct school.

### Staff cannot log in

Check:

1. The staff profile has an email address.
2. The staff account is active.
3. The staff is using the staff ID as the temporary password.
4. The staff is signing in under the correct school.

### Parent cannot see a child

Check:

1. The parent account exists.
2. The parent is linked to the student.
3. The parent and student belong to the same school.
4. The parent is using the correct phone number or email.

### User is stuck on change password

That means the account still has a temporary password. The user must enter the current temporary password, then choose and confirm a new password.
