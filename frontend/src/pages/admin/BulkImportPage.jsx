/**
 * pages/admin/BulkImportPage.jsx
 *
 * Route wrapper that renders BulkImport for a specific entity.
 * Route: /admin/students/import  |  /admin/staff/import
 *
 * Reads ?type=students|staff from the route to configure the
 * BulkImport component, or uses props passed directly.
 */

import React from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import BulkImport from "../../components/admin/BulkImport";
import "./BulkImportPage.css";

const CONFIGS = {
  students: {
    title:        "Bulk Student Import",
    backPath:     "/admin/students",
    backLabel:    "← Back to Students",
    endpoint:     "/api/students/bulk-import/",
    templateCols: [
      "first_name","last_name","email","gender","dob",
      "class_level","guardian_name","guardian_phone",
      "state_of_origin","religion","guardian_email","guardian_relationship",
    ],
    exampleRow:
      "Amaka,Okonkwo,amaka@school.edu.ng,female,2008-05-14,JSS1," +
      "Mrs Okonkwo,08012345678,Lagos,Christianity,parent@example.com,mother",
  },
  staff: {
    title:        "Bulk Staff Import",
    backPath:     "/admin/staff",
    backLabel:    "← Back to Staff",
    endpoint:     "/api/staff/bulk-import/",
    templateCols: [
      "first_name","last_name","email","role",
      "gender","dob","phone","qualification",
      "specialization","date_employed","state_of_origin",
    ],
    exampleRow:
      "Ngozi,Adeyemi,ngozi@school.edu.ng,teacher," +
      "female,1985-03-20,08012345678,bsc,Mathematics,2020-09-01,Lagos",
  },
};

export default function BulkImportPage({ type: typeProp }) {
  const [searchParams] = useSearchParams();
  const navigate       = useNavigate();
  const type           = typeProp || searchParams.get("type") || "students";
  const config         = CONFIGS[type] || CONFIGS.students;

  function handleComplete(result) {
    // After import, wait 2 s then navigate back to the list
    if (result.success_count > 0) {
      setTimeout(() => navigate(config.backPath), 2000);
    }
  }

  return (
    <div className="bip-root">
      <div className="bip-nav">
        <Link to={config.backPath} className="btn btn-ghost btn-sm">
          {config.backLabel}
        </Link>
      </div>

      <div className="bip-card">
        <BulkImport
          endpoint={config.endpoint}
          templateCols={config.templateCols}
          exampleRow={config.exampleRow}
          title={config.title}
          onComplete={handleComplete}
        />
      </div>
    </div>
  );
}