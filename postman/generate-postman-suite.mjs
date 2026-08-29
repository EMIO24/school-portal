import fs from 'node:fs';
import path from 'node:path';

const outDir = new URL('.', import.meta.url);

const collectionPrerequest = `
const cv = pm.collectionVariables;

function ensure(name, value) {
  if (!cv.get(name)) cv.set(name, value);
}

const runId = cv.get('run_id') || String(Date.now());
const suffix = runId.slice(-4);
cv.set('run_id', runId);
cv.set('run_suffix', suffix);
cv.set('today', new Date().toISOString().slice(0, 10));
cv.set('start_ts', new Date().toISOString());
cv.set('end_ts', new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString());

ensure('school_slug', pm.environment.get('school_slug') || 'testschool');
ensure('admin_email', pm.environment.get('admin_email') || 'admin@testschool.ng');
ensure('admin_pass', pm.environment.get('admin_pass') || 'AdminStr0ng#1');
ensure('teacher_email', \`teacher.\${runId}@testschool.ng\`);
ensure('student_email', \`student.\${runId}@testschool.ng\`);
ensure('session_name', \`2024/2025-\${suffix}\`);
ensure('primary_class_level_name', 'JSS1');
ensure('secondary_class_level_name', 'JSS2');
ensure('primary_arm_name', \`A\${suffix}\`);
ensure('secondary_arm_name', \`B\${suffix}\`);
ensure('subject_name', \`Mathematics \${suffix}\`);
ensure('subject_code', \`M\${suffix}\`);
ensure('fee_category_name', \`School Fees \${suffix}\`);
ensure('template_name', \`Test Template \${suffix}\`);
ensure('period_name', \`Period \${suffix}\`);
ensure('period_order_index', String(1000 + Number(suffix)));
ensure('batch_label', \`TEST-BATCH-\${suffix}\`);
ensure('parent_phone', '08012345678');
`;

const collectionTests = `
const cv = pm.collectionVariables;

function jsonBody() {
  try { return pm.response.json(); } catch (error) { return null; }
}

function textBody() {
  return pm.response.text();
}

function setVar(name, value) {
  if (value !== undefined && value !== null && value !== '') {
    cv.set(name, String(value));
  }
}

function getVar(name) {
  return cv.get(name);
}

function expectStatus(allowed, label) {
  pm.test(label || pm.info.requestName, function () {
    pm.expect(allowed, \`Expected status in \${allowed.join(', ')}, got \${pm.response.code}\`).to.include(pm.response.code);
  });
}

function authHeader(token) {
  const headers = [{ key: 'X-School-Slug', value: getVar('school_slug') }];
  if (token) headers.push({ key: 'Authorization', value: \`Bearer \${token}\` });
  return headers;
}

function sendJson(method, route, token, body, callback) {
  pm.sendRequest({
    url: \`\${pm.variables.replaceIn('{{base_url}}')}\${route}\`,
    method,
    header: [
      { key: 'Content-Type', value: 'application/json' },
      ...authHeader(token),
    ],
    body: body === undefined || body === null ? undefined : {
      mode: 'raw',
      raw: typeof body === 'string' ? body : JSON.stringify(body),
    },
  }, callback);
}

function send(method, route, token, callback) {
  pm.sendRequest({
    url: \`\${pm.variables.replaceIn('{{base_url}}')}\${route}\`,
    method,
    header: authHeader(token),
  }, callback);
}
`;

function scriptLines(text) {
  return text.trim().split('\n').map((line) => line.replace(/\r$/, ''));
}

function makeEvent(listen, script) {
  return { listen, script: { type: 'text/javascript', exec: scriptLines(script) } };
}

function jsonRequest({ name, method, route, authVar, body, tests }) {
  const headers = [
    { key: 'X-School-Slug', value: '{{school_slug}}' },
  ];
  if (body !== undefined) {
    headers.push({ key: 'Content-Type', value: 'application/json' });
  }

  const request = {
    method,
    header: headers,
    url: `{{base_url}}${route}`,
  };

  if (authVar) {
    request.auth = {
      type: 'bearer',
      bearer: [{ key: 'token', value: `{{${authVar}}}`, type: 'string' }],
    };
  }

  if (body !== undefined) {
    request.body = {
      mode: 'raw',
      raw: body,
      options: { raw: { language: 'json' } },
    };
  }

  return {
    name,
    request,
    event: [makeEvent('test', tests)],
  };
}

function folder(name, items) {
  return { name, item: items };
}

const items = [
  folder('00 Bootstrap', [
    jsonRequest({
      name: 'Health Check',
      method: 'GET',
      route: '/health/',
      tests: `
expectStatus([200], 'GET /health/');
pm.test('Run variables initialized', function () {
  pm.expect(getVar('run_id')).to.be.a('string');
  pm.expect(getVar('teacher_email')).to.include(getVar('run_id'));
  pm.expect(getVar('student_email')).to.include(getVar('run_id'));
});
`,
    }),
  ]),

  folder('01 Auth', [
    jsonRequest({
      name: 'Admin Login',
      method: 'POST',
      route: '/api/auth/login/',
      body: `{"email":"{{admin_email}}","password":"{{admin_pass}}"}`,
      tests: `
expectStatus([200], 'POST /api/auth/login/ (admin)');
const body = jsonBody();
setVar('admin_token', body?.access);
setVar('refresh_token', body?.refresh);
pm.test('Admin tokens stored', function () {
  pm.expect(getVar('admin_token')).to.be.ok;
  pm.expect(getVar('refresh_token')).to.be.ok;
});
`,
    }),
    jsonRequest({
      name: 'Reject Bad Credentials',
      method: 'POST',
      route: '/api/auth/login/',
      body: `{"email":"wrong@x.com","password":"badpass"}`,
      tests: `expectStatus([401], 'POST /api/auth/login/ rejects bad credentials');`,
    }),
    jsonRequest({
      name: 'Refresh Token',
      method: 'POST',
      route: '/api/auth/token/refresh/',
      body: `{"refresh":"{{refresh_token}}"}`,
      tests: `
expectStatus([200], 'POST /api/auth/token/refresh/');
const body = jsonBody();
setVar('admin_token', body?.access || getVar('admin_token'));
`,
    }),
    jsonRequest({
      name: 'Admin Me',
      method: 'GET',
      route: '/api/auth/me/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/auth/me/');`,
    }),
    jsonRequest({
      name: 'Admin Change Password Temporary',
      method: 'POST',
      route: '/api/auth/change-password/',
      authVar: 'admin_token',
      body: `{"current_password":"{{admin_pass}}","new_password":"TmpT3st@Pass99","confirm_password":"TmpT3st@Pass99"}`,
      tests: `expectStatus([200], 'POST /api/auth/change-password/');`,
    }),
    jsonRequest({
      name: 'Admin Login With Temporary Password',
      method: 'POST',
      route: '/api/auth/login/',
      body: `{"email":"{{admin_email}}","password":"TmpT3st@Pass99"}`,
      tests: `
expectStatus([200], 'POST /api/auth/login/ (temp password)');
const body = jsonBody();
setVar('tmp_token', body?.access);
`,
    }),
    jsonRequest({
      name: 'Restore Admin Password',
      method: 'POST',
      route: '/api/auth/change-password/',
      authVar: 'tmp_token',
      body: `{"current_password":"TmpT3st@Pass99","new_password":"{{admin_pass}}","confirm_password":"{{admin_pass}}"}`,
      tests: `expectStatus([200], 'POST /api/auth/change-password/ (restore)');`,
    }),
    jsonRequest({
      name: 'Admin Re-Login',
      method: 'POST',
      route: '/api/auth/login/',
      body: `{"email":"{{admin_email}}","password":"{{admin_pass}}"}`,
      tests: `
expectStatus([200], 'POST /api/auth/login/ (restore check)');
const body = jsonBody();
setVar('admin_token', body?.access);
setVar('refresh_token', body?.refresh);
`,
    }),
  ]),

  folder('02 Tenant', [
    jsonRequest({
      name: 'School Me',
      method: 'GET',
      route: '/api/school/me/',
      authVar: 'admin_token',
      tests: `
expectStatus([200], 'GET /api/school/me/');
const body = jsonBody();
setVar('school_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'Schools List Or Forbidden',
      method: 'GET',
      route: '/api/schools/',
      authVar: 'admin_token',
      tests: `expectStatus([200, 403], 'GET /api/schools/');`,
    }),
  ]),

  folder('03 Academics', [
    jsonRequest({
      name: 'Create Session',
      method: 'POST',
      route: '/api/sessions/',
      authVar: 'admin_token',
      body: `{"name":"{{session_name}}","start_date":"2024-09-01","end_date":"2025-07-31"}`,
      tests: `
expectStatus([201], 'POST /api/sessions/');
const body = jsonBody();
setVar('session_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Sessions',
      method: 'GET',
      route: '/api/sessions/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/sessions/');`,
    }),
    jsonRequest({
      name: 'Session Detail',
      method: 'GET',
      route: '/api/sessions/{{session_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/sessions/{id}/');`,
    }),
    jsonRequest({
      name: 'Set Current Session',
      method: 'POST',
      route: '/api/sessions/{{session_id}}/set-current/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'POST /api/sessions/{id}/set-current/');`,
    }),
    jsonRequest({
      name: 'Create Term',
      method: 'POST',
      route: '/api/terms/',
      authVar: 'admin_token',
      body: `{"name":"first","session":{{session_id}},"start_date":"2024-09-02","end_date":"2024-12-13"}`,
      tests: `
expectStatus([201], 'POST /api/terms/');
const body = jsonBody();
setVar('term_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Terms',
      method: 'GET',
      route: '/api/terms/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/terms/');`,
    }),
    jsonRequest({
      name: 'Set Current Term',
      method: 'POST',
      route: '/api/terms/{{term_id}}/set-current/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'POST /api/terms/{id}/set-current/');`,
    }),
    jsonRequest({
      name: 'Create Holiday',
      method: 'POST',
      route: '/api/holidays/',
      authVar: 'admin_token',
      body: `{"name":"Test Holiday {{run_suffix}}","start_date":"2024-10-01","end_date":"2024-10-02","term":{{term_id}},"holiday_type":"public"}`,
      tests: `
expectStatus([201], 'POST /api/holidays/');
const body = jsonBody();
setVar('holiday_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Holidays',
      method: 'GET',
      route: '/api/holidays/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/holidays/');`,
    }),
    jsonRequest({
      name: 'Calendar',
      method: 'GET',
      route: '/api/calendar/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/calendar/');`,
    }),
    jsonRequest({
      name: 'Delete Holiday',
      method: 'DELETE',
      route: '/api/holidays/{{holiday_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([204], 'DELETE /api/holidays/{id}/');`,
    }),
  ]),

  folder('04 Enrollment', [
    jsonRequest({
      name: 'Create Or Reuse JSS1 Class Level',
      method: 'POST',
      route: '/api/class-levels/',
      authVar: 'admin_token',
      body: `{"name":"{{primary_class_level_name}}","order_index":1,"is_final_year":false}`,
      tests: `
pm.test('Create or reuse JSS1 class level', function (done) {
  pm.expect([201, 400]).to.include(pm.response.code);
  if (pm.response.code === 201) {
    const body = jsonBody();
    setVar('level_id', body?.id);
    done();
    return;
  }
  send('GET', '/api/class-levels/', getVar('admin_token'), (err, res) => {
    pm.expect(err).to.equal(null);
    pm.expect(res.code).to.equal(200);
    const rows = res.json();
    const item = rows.find((entry) => entry.name === getVar('primary_class_level_name'));
    pm.expect(item, 'Existing JSS1 class level').to.be.ok;
    setVar('level_id', item.id);
    done();
  });
});
`,
    }),
    jsonRequest({
      name: 'List Class Levels',
      method: 'GET',
      route: '/api/class-levels/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/class-levels/');`,
    }),
    jsonRequest({
      name: 'Create Class Arm',
      method: 'POST',
      route: '/api/class-arms/',
      authVar: 'admin_token',
      body: `{"name":"{{primary_arm_name}}","class_level":{{level_id}}}`,
      tests: `
expectStatus([201], 'POST /api/class-arms/');
const body = jsonBody();
setVar('arm_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Class Arms',
      method: 'GET',
      route: '/api/class-arms/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/class-arms/');`,
    }),
    jsonRequest({
      name: 'Create Subject',
      method: 'POST',
      route: '/api/subjects/',
      authVar: 'admin_token',
      body: `{"name":"{{subject_name}}","code":"{{subject_code}}","class_level":{{level_id}}}`,
      tests: `
expectStatus([201], 'POST /api/subjects/');
const body = jsonBody();
setVar('subject_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Subjects',
      method: 'GET',
      route: '/api/subjects/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/subjects/');`,
    }),
    jsonRequest({
      name: 'Subjects By Class',
      method: 'GET',
      route: '/api/subjects/by-class/{{arm_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/subjects/by-class/{arm_id}/');`,
    }),
    jsonRequest({
      name: 'Create Teacher',
      method: 'POST',
      route: '/api/staff/',
      authVar: 'admin_token',
      body: `{"new_email":"{{teacher_email}}","new_first_name":"Test","new_last_name":"Teacher","new_role":"teacher"}`,
      tests: `
expectStatus([201], 'POST /api/staff/ (create teacher)');
const body = jsonBody();
setVar('teacher_id', body?.id);
setVar('teacher_user_id', body?.user);
setVar('teacher_staff_id', body?.staff_id);
`,
    }),
    jsonRequest({
      name: 'List Staff',
      method: 'GET',
      route: '/api/staff/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/staff/');`,
    }),
    jsonRequest({
      name: 'Create Subject Assignment',
      method: 'POST',
      route: '/api/subject-assignments/',
      authVar: 'admin_token',
      body: `{"teacher":{{teacher_id}},"subject":{{subject_id}},"class_arm":{{arm_id}},"session":{{session_id}},"term":{{term_id}}}`,
      tests: `expectStatus([201], 'POST /api/subject-assignments/');`,
    }),
    jsonRequest({
      name: 'Teacher Login',
      method: 'POST',
      route: '/api/auth/login/',
      body: `{"email":"{{teacher_email}}","password":"{{teacher_staff_id}}"}`,
      tests: `
expectStatus([200], 'POST /api/auth/login/ (teacher)');
const body = jsonBody();
setVar('teacher_token', body?.access);
`,
    }),
    jsonRequest({
      name: 'Create Student',
      method: 'POST',
      route: '/api/students/',
      authVar: 'admin_token',
      body: `{"new_email":"{{student_email}}","new_first_name":"Test","new_last_name":"Student","current_class":{{arm_id}}}`,
      tests: `
expectStatus([201], 'POST /api/students/ (create student)');
const body = jsonBody();
setVar('student_profile_id', body?.id);
setVar('student_user_id', body?.user);
setVar('student_adm_num', body?.admission_number);
`,
    }),
    jsonRequest({
      name: 'List Students',
      method: 'GET',
      route: '/api/students/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/students/');`,
    }),
    jsonRequest({
      name: 'Students By Class',
      method: 'GET',
      route: '/api/students/by-class/{{arm_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/students/by-class/{arm_id}/');`,
    }),
    jsonRequest({
      name: 'Assign Student Class',
      method: 'POST',
      route: '/api/students/{{student_profile_id}}/assign-class/',
      authVar: 'admin_token',
      body: `{"class_arm":{{arm_id}}}`,
      tests: `expectStatus([200], 'POST /api/students/{id}/assign-class/');`,
    }),
    jsonRequest({
      name: 'Student Login',
      method: 'POST',
      route: '/api/auth/login/',
      body: `{"email":"{{student_email}}","password":"{{student_adm_num}}"}`,
      tests: `
expectStatus([200], 'POST /api/auth/login/ (student)');
const body = jsonBody();
setVar('student_token', body?.access);
`,
    }),
    jsonRequest({
      name: 'List Subject Assignments',
      method: 'GET',
      route: '/api/subject-assignments/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/subject-assignments/');`,
    }),
    jsonRequest({
      name: 'Subject Assignments Grid',
      method: 'GET',
      route: '/api/subject-assignments/grid/?term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/subject-assignments/grid/');`,
    }),
  ]),

  folder('05 Attendance', [
    jsonRequest({
      name: 'Create Attendance Session',
      method: 'POST',
      route: '/api/attendance/sessions/',
      authVar: 'teacher_token',
      body: `{"class_arm":{{arm_id}},"term":{{term_id}},"date":"{{today}}"}`,
      tests: `
expectStatus([201], 'POST /api/attendance/sessions/');
const body = jsonBody();
setVar('att_session_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Attendance Sessions',
      method: 'GET',
      route: '/api/attendance/sessions/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/attendance/sessions/');`,
    }),
    jsonRequest({
      name: 'Attendance Session Detail',
      method: 'GET',
      route: '/api/attendance/sessions/{{att_session_id}}/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/attendance/sessions/{id}/');`,
    }),
    jsonRequest({
      name: 'Submit Attendance Records',
      method: 'PATCH',
      route: '/api/attendance/sessions/{{att_session_id}}/submit/',
      authVar: 'teacher_token',
      body: `{"records":[{"student_id":{{student_user_id}},"status":"present"}]}`,
      tests: `expectStatus([200], 'PATCH /api/attendance/sessions/{id}/submit/');`,
    }),
    jsonRequest({
      name: 'Finalize Attendance Session',
      method: 'PATCH',
      route: '/api/attendance/sessions/{{att_session_id}}/finalize/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'PATCH /api/attendance/sessions/{id}/finalize/');`,
    }),
    jsonRequest({
      name: 'Attendance Student Report',
      method: 'GET',
      route: '/api/attendance/sessions/report/?student={{student_user_id}}&term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/attendance/sessions/report/');`,
    }),
    jsonRequest({
      name: 'Attendance Class Report',
      method: 'GET',
      route: '/api/attendance/sessions/class-report/?class_arm={{arm_id}}&term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/attendance/sessions/class-report/');`,
    }),
    jsonRequest({
      name: 'Low Attendance Report',
      method: 'GET',
      route: '/api/attendance/sessions/low-attendance/?term={{term_id}}&threshold=75',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/attendance/sessions/low-attendance/');`,
    }),
  ]),

  folder('06 Gradebook', [
    jsonRequest({
      name: 'Grade Scale',
      method: 'GET',
      route: '/api/gradebook/entries/grade-scale/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/gradebook/entries/grade-scale/');`,
    }),
    jsonRequest({
      name: 'Filtered Gradebook Entries',
      method: 'GET',
      route: '/api/gradebook/entries/?class_arm={{arm_id}}&subject={{subject_id}}&term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/gradebook/entries/ (filtered)');`,
    }),
    jsonRequest({
      name: 'Bulk Update Scores',
      method: 'POST',
      route: '/api/gradebook/entries/bulk-update/',
      authVar: 'teacher_token',
      body: `{"class_arm":{{arm_id}},"subject":{{subject_id}},"term":{{term_id}},"session":{{session_id}},"scores":[{"student_id":{{student_user_id}},"first_test":10,"second_test":10,"assignment":5,"project":5,"practical":0,"exam_score":50}]}`,
      tests: `expectStatus([200], 'POST /api/gradebook/entries/bulk-update/');`,
    }),
    jsonRequest({
      name: 'Publish Scores',
      method: 'POST',
      route: '/api/gradebook/entries/publish/?class_arm={{arm_id}}&subject={{subject_id}}&term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'POST /api/gradebook/entries/publish/');`,
    }),
    jsonRequest({
      name: 'Affective List',
      method: 'GET',
      route: '/api/gradebook/affective/?class_arm={{arm_id}}&term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/gradebook/affective/');`,
    }),
    jsonRequest({
      name: 'Update Affective',
      method: 'PUT',
      route: '/api/gradebook/affective/student/{{student_user_id}}/term/{{term_id}}/',
      authVar: 'teacher_token',
      body: `{"class_arm":{{arm_id}},"punctuality":4,"neatness":5,"attentiveness":4,"honesty":5,"politeness":4,"cooperation":5}`,
      tests: `expectStatus([200], 'PUT /api/gradebook/affective/student/{id}/term/{id}/');`,
    }),
    jsonRequest({
      name: 'Psychomotor List',
      method: 'GET',
      route: '/api/gradebook/psychomotor/?class_arm={{arm_id}}&term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/gradebook/psychomotor/');`,
    }),
    jsonRequest({
      name: 'Update Psychomotor',
      method: 'PUT',
      route: '/api/gradebook/psychomotor/student/{{student_user_id}}/term/{{term_id}}/',
      authVar: 'teacher_token',
      body: `{"class_arm":{{arm_id}},"handwriting":4,"drawing":3,"sports":5,"music":4,"verbal_fluency":4,"craft":3}`,
      tests: `expectStatus([200], 'PUT /api/gradebook/psychomotor/student/{id}/term/{id}/');`,
    }),
  ]),

  folder('07 Results', [
    jsonRequest({
      name: 'Compute Positions',
      method: 'POST',
      route: '/api/results/positions/compute/?class_arm={{arm_id}}&term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'POST /api/results/positions/compute/');`,
    }),
    jsonRequest({
      name: 'Class Results',
      method: 'GET',
      route: '/api/results/class-results/?class_arm={{arm_id}}&term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/results/class-results/');`,
    }),
    jsonRequest({
      name: 'Student Remarks',
      method: 'GET',
      route: '/api/results/remarks/{{student_user_id}}/?term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/results/remarks/{student_id}/');`,
    }),
    jsonRequest({
      name: 'Patch Student Remarks',
      method: 'PATCH',
      route: '/api/results/remarks/{{student_user_id}}/?term={{term_id}}',
      authVar: 'admin_token',
      body: `{"principal_remark":"Excellent performance","teacher_remark":"Keep it up"}`,
      tests: `expectStatus([200], 'PATCH /api/results/remarks/{student_id}/');`,
    }),
    jsonRequest({
      name: 'Slip Data Preview',
      method: 'GET',
      route: '/api/results/slip-data/{{student_user_id}}/?term={{term_id}}',
      authVar: 'student_token',
      tests: `expectStatus([200], 'GET /api/results/slip-data/{student_id}/');`,
    }),
    jsonRequest({
      name: 'Result Slip PDF',
      method: 'GET',
      route: '/api/results/slip/{{student_user_id}}/?term={{term_id}}',
      authVar: 'student_token',
      tests: `expectStatus([200], 'GET /api/results/slip/{student_id}/ (PDF)');`,
    }),
    jsonRequest({
      name: 'Broadsheet PDF',
      method: 'GET',
      route: '/api/results/broadsheet/{{arm_id}}/?term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/results/broadsheet/{class_arm_id}/ (PDF)');`,
    }),
  ]),

  folder('08 Scratch Cards', [
    jsonRequest({
      name: 'Generate Scratch Cards',
      method: 'POST',
      route: '/api/scratch-cards/generate/',
      authVar: 'admin_token',
      body: `{"term_id":{{term_id}},"quantity":5,"batch_name":"{{batch_label}}"}`,
      tests: `
expectStatus([200], 'POST /api/scratch-cards/generate/');
const lines = textBody().trim().split(/\\r?\\n/);
if (lines.length > 1) {
  const cols = lines[1].split(',');
  setVar('card_serial', cols[0]);
  setVar('card_pin', cols[1]);
}
`,
    }),
    jsonRequest({
      name: 'List Scratch Cards',
      method: 'GET',
      route: '/api/scratch-cards/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/scratch-cards/');`,
    }),
    jsonRequest({
      name: 'Scratch Card Batch Stats',
      method: 'GET',
      route: '/api/scratch-cards/batch-stats/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/scratch-cards/batch-stats/');`,
    }),
    jsonRequest({
      name: 'Scratch Card Unused CSV',
      method: 'GET',
      route: '/api/scratch-cards/unused-csv/?batch={{batch_label}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/scratch-cards/unused-csv/');`,
    }),
    jsonRequest({
      name: 'Public Result Check',
      method: 'POST',
      route: '/api/results/check/',
      body: `{"serial_number":"{{card_serial}}","pin":"{{card_pin}}","admission_number":"{{student_adm_num}}"}`,
      tests: `expectStatus([200], 'POST /api/results/check/ (public scratch-card)');`,
    }),
  ]),

  folder('09 CBT', [
    jsonRequest({
      name: 'Create Topic',
      method: 'POST',
      route: '/api/cbt/topics/',
      authVar: 'teacher_token',
      body: `{"name":"Algebra Basics {{run_suffix}}","subject":{{subject_id}},"class_level":{{level_id}}}`,
      tests: `
expectStatus([201], 'POST /api/cbt/topics/');
const body = jsonBody();
setVar('topic_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Topics',
      method: 'GET',
      route: '/api/cbt/topics/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/cbt/topics/');`,
    }),
    jsonRequest({
      name: 'Create MCQ Question',
      method: 'POST',
      route: '/api/cbt/questions/',
      authVar: 'teacher_token',
      body: `{"topic":{{topic_id}},"subject":{{subject_id}},"class_level":{{level_id}},"question_text":"What is 2+2?","question_type":"mcq","difficulty":"easy","cognitive_level":"knowledge","options":[{"id":"A","text":"3"},{"id":"B","text":"4"},{"id":"C","text":"5"},{"id":"D","text":"6"}],"correct_answer":"B","explanation":"2 plus 2 equals 4.","is_active":true}`,
      tests: `
expectStatus([201], 'POST /api/cbt/questions/ (MCQ)');
const body = jsonBody();
setVar('question_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'Create Fill Blank Question',
      method: 'POST',
      route: '/api/cbt/questions/',
      authVar: 'teacher_token',
      body: `{"topic":{{topic_id}},"subject":{{subject_id}},"class_level":{{level_id}},"question_text":"The capital of Nigeria is ___.","question_type":"fill_blank","difficulty":"easy","cognitive_level":"knowledge","options":[],"correct_answer":"Abuja","explanation":"Abuja is Nigeria's capital city.","is_active":true}`,
      tests: `expectStatus([201], 'POST /api/cbt/questions/ (fill_blank)');`,
    }),
    jsonRequest({
      name: 'List Questions',
      method: 'GET',
      route: '/api/cbt/questions/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/cbt/questions/');`,
    }),
    jsonRequest({
      name: 'Question Stats',
      method: 'GET',
      route: '/api/cbt/questions/stats/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/cbt/questions/stats/');`,
    }),
    jsonRequest({
      name: 'Bulk Import Questions',
      method: 'POST',
      route: '/api/cbt/questions/bulk-import/',
      authVar: 'teacher_token',
      body: `[{"topic":{{topic_id}},"subject":{{subject_id}},"class_level":{{level_id}},"question_text":"5 x 5 = ?","question_type":"mcq","difficulty":"easy","cognitive_level":"knowledge","options":[{"id":"A","text":"20"},{"id":"B","text":"25"},{"id":"C","text":"30"},{"id":"D","text":"35"}],"correct_answer":"B","is_active":true}]`,
      tests: `expectStatus([201], 'POST /api/cbt/questions/bulk-import/');`,
    }),
    jsonRequest({
      name: 'Create CBT Exam',
      method: 'POST',
      route: '/api/cbt/exams/',
      authVar: 'teacher_token',
      body: `{"title":"Test Maths Exam {{run_suffix}}","subject":{{subject_id}},"term":{{term_id}},"session":{{session_id}},"class_arms":[{{arm_id}}],"duration_minutes":60,"start_datetime":"{{start_ts}}","end_datetime":"{{end_ts}}","instructions":"Answer all questions.","selection_mode":"manual","manual_questions":[{{question_id}}],"random_config":[],"randomize_questions":false,"randomize_options":false,"allow_review":true,"show_score_immediately":true,"status":"published"}`,
      tests: `
expectStatus([201], 'POST /api/cbt/exams/');
const body = jsonBody();
setVar('exam_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List CBT Exams',
      method: 'GET',
      route: '/api/cbt/exams/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/cbt/exams/');`,
    }),
    jsonRequest({
      name: 'CBT Exam Detail',
      method: 'GET',
      route: '/api/cbt/exams/{{exam_id}}/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/cbt/exams/{id}/');`,
    }),
    jsonRequest({
      name: 'Student Available Exams',
      method: 'GET',
      route: '/api/cbt/exams/available/',
      authVar: 'student_token',
      tests: `expectStatus([200], 'GET /api/cbt/exams/available/ (student)');`,
    }),
    jsonRequest({
      name: 'Start CBT Exam',
      method: 'POST',
      route: '/api/cbt/exams/{{exam_id}}/start/',
      authVar: 'student_token',
      tests: `expectStatus([200], 'POST /api/cbt/exams/{id}/start/');`,
    }),
    jsonRequest({
      name: 'CBT Exam Status',
      method: 'GET',
      route: '/api/cbt/exams/{{exam_id}}/status/',
      authVar: 'student_token',
      tests: `expectStatus([200], 'GET /api/cbt/exams/{id}/status/');`,
    }),
    jsonRequest({
      name: 'Save CBT Answer',
      method: 'POST',
      route: '/api/cbt/exams/{{exam_id}}/save-answer/',
      authVar: 'student_token',
      body: `{"question_id":{{question_id}},"selected_option":"B"}`,
      tests: `expectStatus([200], 'POST /api/cbt/exams/{id}/save-answer/');`,
    }),
    jsonRequest({
      name: 'Log Tab Switch',
      method: 'POST',
      route: '/api/cbt/exams/{{exam_id}}/log-tab-switch/',
      authVar: 'student_token',
      tests: `expectStatus([200], 'POST /api/cbt/exams/{id}/log-tab-switch/');`,
    }),
    jsonRequest({
      name: 'Submit CBT Exam',
      method: 'POST',
      route: '/api/cbt/exams/{{exam_id}}/submit/',
      authVar: 'student_token',
      tests: `expectStatus([200], 'POST /api/cbt/exams/{id}/submit/');`,
    }),
  ]),

  folder('10 Fees', [
    jsonRequest({
      name: 'Create Fee Category',
      method: 'POST',
      route: '/api/fees/categories/',
      authVar: 'admin_token',
      body: `{"name":"{{fee_category_name}}","description":"Main term school fees"}`,
      tests: `
expectStatus([201], 'POST /api/fees/categories/');
const body = jsonBody();
setVar('fee_cat_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Fee Categories',
      method: 'GET',
      route: '/api/fees/categories/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/fees/categories/');`,
    }),
    jsonRequest({
      name: 'Update Fee Category',
      method: 'PUT',
      route: '/api/fees/categories/{{fee_cat_id}}/',
      authVar: 'admin_token',
      body: `{"name":"{{fee_category_name}} Updated"}`,
      tests: `expectStatus([200], 'PUT /api/fees/categories/{id}/');`,
    }),
    jsonRequest({
      name: 'Create Fee Schedule',
      method: 'POST',
      route: '/api/fees/schedule/',
      authVar: 'admin_token',
      body: `{"term_id":{{term_id}},"schedules":[{"class_level_id":{{level_id}},"fee_category_id":{{fee_cat_id}},"amount":25000,"due_date":"2024-09-30"}]}`,
      tests: `expectStatus([201], 'POST /api/fees/schedule/ (bulk)');`,
    }),
    jsonRequest({
      name: 'List Fee Schedules',
      method: 'GET',
      route: '/api/fees/schedule/?term={{term_id}}',
      authVar: 'admin_token',
      tests: `
expectStatus([200], 'GET /api/fees/schedule/');
const body = jsonBody();
setVar('fee_schedule_id', Array.isArray(body) && body[0] ? body[0].id : '');
`,
    }),
    jsonRequest({
      name: 'Student Fee Summary',
      method: 'GET',
      route: '/api/fees/student/{{student_profile_id}}/?term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/fees/student/{id}/');`,
    }),
    jsonRequest({
      name: 'Manual Fee Payment',
      method: 'POST',
      route: '/api/fees/pay/manual/',
      authVar: 'admin_token',
      body: `{"student_id":{{student_profile_id}},"fee_schedule_id":{{fee_schedule_id}},"amount_paid":25000,"payment_date":"{{today}}","method":"cash"}`,
      tests: `
expectStatus([201], 'POST /api/fees/pay/manual/');
const body = jsonBody();
setVar('payment_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'Fee Receipt PDF',
      method: 'GET',
      route: '/api/fees/receipts/{{payment_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/fees/receipts/{id}/ (PDF)');`,
    }),
    jsonRequest({
      name: 'Outstanding Fees',
      method: 'GET',
      route: '/api/fees/outstanding/?term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/fees/outstanding/');`,
    }),
    jsonRequest({
      name: 'Outstanding Fees By Class',
      method: 'GET',
      route: '/api/fees/outstanding/?term={{term_id}}&class_arm={{arm_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/fees/outstanding/ (filtered by class_arm)');`,
    }),
    jsonRequest({
      name: 'Initiate Paystack Payment',
      method: 'POST',
      route: '/api/fees/pay/initiate/',
      authVar: 'admin_token',
      body: `{"student_id":{{student_profile_id}},"fee_schedule_ids":[{{fee_schedule_id}}]}`,
      tests: `expectStatus([200, 502], 'POST /api/fees/pay/initiate/');`,
    }),
  ]),

  folder('11 Timetable', [
    jsonRequest({
      name: 'Create Period',
      method: 'POST',
      route: '/api/timetable/periods/',
      authVar: 'admin_token',
      body: `{"name":"{{period_name}}","start_time":"08:00:00","end_time":"08:45:00","order_index":{{period_order_index}},"is_break":false}`,
      tests: `
expectStatus([201], 'POST /api/timetable/periods/');
const body = jsonBody();
setVar('period_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Periods',
      method: 'GET',
      route: '/api/timetable/periods/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/timetable/periods/');`,
    }),
    jsonRequest({
      name: 'Create Timetable Entry',
      method: 'POST',
      route: '/api/timetable/entries/',
      authVar: 'admin_token',
      body: `{"class_arm":{{arm_id}},"subject":{{subject_id}},"teacher":{{teacher_user_id}},"period":{{period_id}},"day_of_week":"MON","term":{{term_id}}}`,
      tests: `
expectStatus([201], 'POST /api/timetable/entries/');
const body = jsonBody();
setVar('tt_entry_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Timetable Entries',
      method: 'GET',
      route: '/api/timetable/entries/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/timetable/entries/');`,
    }),
    jsonRequest({
      name: 'Timetable Grid',
      method: 'GET',
      route: '/api/timetable/entries/grid/?class_arm={{arm_id}}&term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/timetable/entries/grid/');`,
    }),
    jsonRequest({
      name: 'Timetable By Class',
      method: 'GET',
      route: '/api/timetable/entries/by-class/{{arm_id}}/?term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/timetable/entries/by-class/{id}/');`,
    }),
    jsonRequest({
      name: 'Timetable By Teacher',
      method: 'GET',
      route: '/api/timetable/entries/by-teacher/{{teacher_user_id}}/?term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/timetable/entries/by-teacher/{id}/');`,
    }),
    jsonRequest({
      name: 'My Timetable',
      method: 'GET',
      route: '/api/timetable/entries/my-timetable/?term={{term_id}}',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/timetable/entries/my-timetable/');`,
    }),
    jsonRequest({
      name: 'Teacher Load',
      method: 'GET',
      route: '/api/timetable/entries/teacher-load/?teacher={{teacher_user_id}}&term={{term_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/timetable/entries/teacher-load/');`,
    }),
  ]),

  folder('12 Notifications', [
    jsonRequest({
      name: 'Create Notification Template',
      method: 'POST',
      route: '/api/notifications/templates/',
      authVar: 'admin_token',
      body: `{"name":"{{template_name}}","type":"sms","category":"general","body":"Hello {{student_name}}, this is a test."}`,
      tests: `
expectStatus([201], 'POST /api/notifications/templates/');
const body = jsonBody();
setVar('template_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'List Notification Templates',
      method: 'GET',
      route: '/api/notifications/templates/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/notifications/templates/');`,
    }),
    jsonRequest({
      name: 'Update Notification Template',
      method: 'PUT',
      route: '/api/notifications/templates/{{template_id}}/',
      authVar: 'admin_token',
      body: `{"name":"{{template_name}} Updated","type":"sms","category":"general","body":"Hi {{student_name}}!"}`,
      tests: `expectStatus([200], 'PUT /api/notifications/templates/{id}/');`,
    }),
    jsonRequest({
      name: 'Send Notification',
      method: 'POST',
      route: '/api/notifications/send/',
      authVar: 'admin_token',
      body: `{"channel":"sms","template_id":{{template_id}},"recipient_ids":[{{student_user_id}}]}`,
      tests: `expectStatus([200, 201, 207, 500], 'POST /api/notifications/send/');`,
    }),
    jsonRequest({
      name: 'Notification Logs',
      method: 'GET',
      route: '/api/notifications/logs/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/notifications/logs/');`,
    }),
    jsonRequest({
      name: 'Delete Notification Template',
      method: 'DELETE',
      route: '/api/notifications/templates/{{template_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([204], 'DELETE /api/notifications/templates/{id}/');`,
    }),
  ]),

  folder('13 Analytics', [
    jsonRequest({
      name: 'Analytics Overview',
      method: 'GET',
      route: '/api/analytics/overview/',
      authVar: 'admin_token',
      tests: `expectStatus([200, 204], 'GET /api/analytics/overview/');`,
    }),
    jsonRequest({
      name: 'Analytics Refresh',
      method: 'POST',
      route: '/api/analytics/refresh/',
      authVar: 'admin_token',
      tests: `expectStatus([200, 202], 'POST /api/analytics/refresh/');`,
    }),
    jsonRequest({
      name: 'Analytics By Class',
      method: 'GET',
      route: '/api/analytics/class/{{arm_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([200, 204, 404], 'GET /api/analytics/class/{id}/');`,
    }),
    jsonRequest({
      name: 'Analytics Student Trends',
      method: 'GET',
      route: '/api/analytics/student/{{student_user_id}}/trends/',
      authVar: 'admin_token',
      tests: `expectStatus([200, 204, 404], 'GET /api/analytics/student/{id}/trends/');`,
    }),
    jsonRequest({
      name: 'Analytics Transcript',
      method: 'GET',
      route: '/api/analytics/transcript/{{student_user_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([200, 404], 'GET /api/analytics/transcript/{id}/');`,
    }),
    jsonRequest({
      name: 'Reports Transcript',
      method: 'GET',
      route: '/api/reports/transcript/{{student_user_id}}/',
      authVar: 'admin_token',
      tests: `expectStatus([200, 404], 'GET /api/reports/transcript/{id}/');`,
    }),
  ]),

  folder('14 Promotion', [
    jsonRequest({
      name: 'Create Promotion Criteria',
      method: 'POST',
      route: '/api/promotion/criteria/',
      authVar: 'admin_token',
      body: `{"class_level_id":{{level_id}},"min_subjects_to_pass":3,"min_average_score":40,"min_attendance_pct":50,"auto_promote_if_met":false}`,
      tests: `expectStatus([201], 'POST /api/promotion/criteria/');`,
    }),
    jsonRequest({
      name: 'List Promotion Criteria',
      method: 'GET',
      route: '/api/promotion/criteria/',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'GET /api/promotion/criteria/');`,
    }),
    jsonRequest({
      name: 'Evaluate Promotion',
      method: 'POST',
      route: '/api/promotion/evaluate/?session={{session_id}}&class_level={{level_id}}',
      authVar: 'admin_token',
      tests: `expectStatus([200], 'POST /api/promotion/evaluate/');`,
    }),
    jsonRequest({
      name: 'Create Or Reuse JSS2 Class Level',
      method: 'POST',
      route: '/api/class-levels/',
      authVar: 'admin_token',
      body: `{"name":"{{secondary_class_level_name}}","order_index":2,"is_final_year":false}`,
      tests: `
pm.test('Create or reuse JSS2 class level', function (done) {
  pm.expect([201, 400]).to.include(pm.response.code);
  if (pm.response.code === 201) {
    const body = jsonBody();
    setVar('level2_id', body?.id);
    done();
    return;
  }
  send('GET', '/api/class-levels/', getVar('admin_token'), (err, res) => {
    pm.expect(err).to.equal(null);
    pm.expect(res.code).to.equal(200);
    const rows = res.json();
    const item = rows.find((entry) => entry.name === getVar('secondary_class_level_name'));
    pm.expect(item, 'Existing JSS2 class level').to.be.ok;
    setVar('level2_id', item.id);
    done();
  });
});
`,
    }),
    jsonRequest({
      name: 'Create Secondary Class Arm',
      method: 'POST',
      route: '/api/class-arms/',
      authVar: 'admin_token',
      body: `{"name":"{{secondary_arm_name}}","class_level":{{level2_id}}}`,
      tests: `
expectStatus([201], 'POST /api/class-arms/ (secondary)');
const body = jsonBody();
setVar('arm2_id', body?.id);
`,
    }),
    jsonRequest({
      name: 'Execute Promotion',
      method: 'POST',
      route: '/api/promotion/execute/',
      authVar: 'admin_token',
      body: `[{"student_id":{{student_profile_id}},"session_id":{{session_id}},"to_class_id":{{arm2_id}},"decision":"promoted","criteria_met":true,"notes":"Test promotion"}]`,
      tests: `expectStatus([200], 'POST /api/promotion/execute/');`,
    }),
  ]),

  folder('15 Parent', [
    jsonRequest({
      name: 'Parent OTP Request',
      method: 'POST',
      route: '/api/auth/parent/otp-request/',
      body: `{"phone":"{{parent_phone}}"}`,
      tests: `expectStatus([200], 'POST /api/auth/parent/otp-request/');`,
    }),
    jsonRequest({
      name: 'Parent OTP Verify Rejects Invalid Code',
      method: 'POST',
      route: '/api/auth/parent/otp-verify/',
      body: `{"phone":"{{parent_phone}}","otp":"000000"}`,
      tests: `expectStatus([401], 'POST /api/auth/parent/otp-verify/ rejects invalid OTP');`,
    }),
  ]),

  folder('16 Profile And Security', [
    jsonRequest({
      name: 'Teacher Me',
      method: 'GET',
      route: '/api/auth/me/',
      authVar: 'teacher_token',
      tests: `expectStatus([200], 'GET /api/auth/me/ (teacher)');`,
    }),
    jsonRequest({
      name: 'Teacher Profile Update',
      method: 'PATCH',
      route: '/api/auth/me/',
      authVar: 'teacher_token',
      body: `{"first_name":"Updated","last_name":"Teacher"}`,
      tests: `expectStatus([200], 'PATCH /api/auth/me/');`,
    }),
    jsonRequest({
      name: 'Student Cannot Create Staff',
      method: 'POST',
      route: '/api/staff/',
      authVar: 'student_token',
      body: `{"email":"hacker@x.com","first_name":"H","last_name":"X","password":"hacked","role":"teacher"}`,
      tests: `expectStatus([401, 403], 'Student cannot create staff');`,
    }),
    jsonRequest({
      name: 'Student Cannot Create Fee Category',
      method: 'POST',
      route: '/api/fees/categories/',
      authVar: 'student_token',
      body: `{"name":"Fake Fee"}`,
      tests: `expectStatus([401, 403], 'Student cannot create fee categories');`,
    }),
    jsonRequest({
      name: 'Unauthenticated Gradebook Request Rejected',
      method: 'GET',
      route: '/api/gradebook/entries/',
      tests: `expectStatus([401], 'Unauthenticated request rejected');`,
    }),
  ]),
];

const collection = {
  info: {
    _postman_id: '8c3c74f0-1fd0-45be-a6bf-6a1b38ba6cf6',
    name: 'School Portal API Tests',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
    description: 'Postman version of the school portal end-to-end API tests. Collection variables store JWT tokens, generated fixture IDs, and run-scoped emails so the suite can run in Collection Runner or Newman without manual token copying.',
  },
  event: [
    makeEvent('prerequest', collectionPrerequest),
    makeEvent('test', collectionTests),
  ],
  variable: [
    { key: 'school_slug', value: 'testschool' },
    { key: 'admin_email', value: 'admin@testschool.ng' },
    { key: 'admin_pass', value: 'AdminStr0ng#1' },
  ],
  item: items,
};

const environment = {
  id: '3fb6fb37-4214-4554-b52e-8c6be10b30c4',
  name: 'School Portal Local',
  values: [
    { key: 'base_url', value: 'http://localhost:8000', type: 'text', enabled: true },
    { key: 'school_slug', value: 'testschool', type: 'text', enabled: true },
    { key: 'admin_email', value: 'admin@testschool.ng', type: 'text', enabled: true },
    { key: 'admin_pass', value: 'AdminStr0ng#1', type: 'text', enabled: true },
  ],
  _postman_variable_scope: 'environment',
  _postman_exported_at: new Date().toISOString(),
  _postman_exported_using: 'Codex',
};

const readme = `# Postman Test Suite

Files:

- \`school-portal-api-tests.postman_collection.json\`
- \`school-portal-local.postman_environment.json\`

What this collection handles automatically:

- stores admin, teacher, and student JWTs in collection variables
- generates run-specific teacher and student emails so reruns do not collide
- persists shared IDs like \`session_id\`, \`term_id\`, \`student_user_id\`, and \`exam_id\`
- uses Postman's cookie jar automatically if any endpoint sets cookies
- avoids session/cookie coupling by authenticating all protected requests with bearer tokens

How to run:

1. Import the collection and environment into Postman.
2. Select the \`School Portal Local\` environment.
3. Set \`base_url\`, \`school_slug\`, \`admin_email\`, and \`admin_pass\` if your local values differ.
4. Run the full collection in Collection Runner.

Optional Newman command:

\`\`\`bash
newman run postman/school-portal-api-tests.postman_collection.json \\
  -e postman/school-portal-local.postman_environment.json
\`\`\`

Notes:

- The parent dashboard/children endpoints are not included because they require a pre-linked parent account.
- External integrations are treated as acceptable when they return their expected non-local statuses:
  - Paystack initiate: \`200\` or \`502\`
  - Notifications send: \`200\`, \`201\`, \`207\`, or \`500\`
  - Analytics transcript/trends endpoints accept \`404\` when no extra data exists yet.
`;

fs.writeFileSync(new URL('school-portal-api-tests.postman_collection.json', outDir), JSON.stringify(collection, null, 2) + '\n');
fs.writeFileSync(new URL('school-portal-local.postman_environment.json', outDir), JSON.stringify(environment, null, 2) + '\n');
fs.writeFileSync(new URL('README.md', outDir), readme);

console.log('Generated Postman collection and environment in postman/.');
