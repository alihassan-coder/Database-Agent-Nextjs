                 │
                 ▼
┌──────────────────────────────────────────┐
│                 Frontend                 │
│  (User chat UI / API / LangServe)        │
└──────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│             Agent Orchestrator           │
│        (LangGraph or LangChain)          │
│------------------------------------------│
│  - LLM decision logic                    │
│  - Schema understanding                  │
│  - Tool calling (DB, RAG, etc.)          │
│  - Memory and context                    │
└──────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│              Data Layer                  │
│------------------------------------------│
│  - PostgreSQL (structured data)          │
│  - Vector store(RAG) (unstructured data) │
│  - Schema metadata cache                 │
└──────────────────────────────────────────┘






Full DB Schema: {
  "total_tables": 10,
  "database_type": "postgresql",
  "tables": {
    "send": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('send_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "email",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "password",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    },
    "admin2": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('admin2_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "admin_name",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "admin_email",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "password",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "created_at",
          "type": "TIMESTAMP",
          "nullable": true,
          "primary_key": false,
          "default": "CURRENT_TIMESTAMP",
          "comment": null
        },
        {
          "name": "updated_at",
          "type": "TIMESTAMP",
          "nullable": true,
          "primary_key": false,
          "default": "CURRENT_TIMESTAMP",
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "admin2_email_key",
          "columns": [
            "admin_email"
          ],
          "unique": true
        }
      ],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    },
    "orders": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('orders_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "customer_name",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "email",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "total",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "orders_email_key",
          "columns": [
            "email"
          ],
          "unique": true
        }
      ],
      "row_count": 1,
      "example_rows": [
        {
          "id": 1,
          "customer_name": "alihassan",
          "email": "alibinsalman786@gmail.com",
          "total": 90000
        }
      ],
      "comment": {
        "text": null
      }
    },
    "contactus": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('contactus_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "name",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "email",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "subject",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "message",
          "type": "TEXT",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "contactus_email_key",
          "columns": [
            "email"
          ],
          "unique": true
        }
      ],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    },
    "admin": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('admin_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "name",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "email",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "password",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "created_at",
          "type": "TIMESTAMP",
          "nullable": true,
          "primary_key": false,
          "default": "CURRENT_TIMESTAMP",
          "comment": null
        },
        {
          "name": "updated_at",
          "type": "TIMESTAMP",
          "nullable": true,
          "primary_key": false,
          "default": "CURRENT_TIMESTAMP",
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "admin_email_key",
          "columns": [
            "email"
          ],
          "unique": true
        }
      ],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    },
    "teacher": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('teacher_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "name",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "email",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "phone",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "teacher_email_key",
          "columns": [
            "email"
          ],
          "unique": true
        }
      ],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    },
    "user": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('user_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "name",
          "type": "VARCHAR",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "email",
          "type": "VARCHAR",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "password",
          "type": "VARCHAR",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "status",
          "type": "VARCHAR",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "user_email_key",
          "columns": [
            "email"
          ],
          "unique": true
        }
      ],
      "row_count": 1,
      "example_rows": [
        {
          "user": "neondb_owner"
        }
      ],
      "comment": {
        "text": null
      }
    },
    "student_names": {
      "columns": [
        {
          "name": "id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('student_names_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "rollno",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "name",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "id"
      ],
      "foreign_keys": [],
      "indexes": [],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    },
    "student": {
      "columns": [
        {
          "name": "student_id",
          "type": "INTEGER",
          "nullable": false,
          "primary_key": true,
          "default": "nextval('student_student_id_seq'::regclass)",
          "comment": null
        },
        {
          "name": "name",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "email",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "student_rollno",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "extracurricular_activities_marks",
          "type": "INTEGER",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "student_id"
      ],
      "foreign_keys": [],
      "indexes": [
        {
          "name": "student_email_key",
          "columns": [
            "email"
          ],
          "unique": true
        },
        {
          "name": "student_student_rollno_key",
          "columns": [
            "student_rollno"
          ],
          "unique": true
        }
      ],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    },
    "marks": {
      "columns": [
        {
          "name": "student_rollno",
          "type": "VARCHAR(255)",
          "nullable": false,
          "primary_key": true,
          "default": null,
          "comment": null
        },
        {
          "name": "name",
          "type": "VARCHAR(255)",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "totle_marks",
          "type": "INTEGER",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        },
        {
          "name": "by_test",
          "type": "INTEGER",
          "nullable": true,
          "primary_key": false,
          "default": null,
          "comment": null
        }
      ],
      "primary_keys": [
        "student_rollno"
      ],
      "foreign_keys": [
        {
          "column": "student_rollno",
          "ref_table": "student",
          "ref_column": "student_rollno",
          "on_delete": "RESTRICT",
          "on_update": "RESTRICT"
        }
      ],
      "indexes": [],
      "row_count": 0,
      "example_rows": [],
      "comment": {
        "text": null
      }
    }
  }
}