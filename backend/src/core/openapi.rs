//! Hand-written OpenAPI document plus Swagger UI (`/docs`) and Scalar (`/sdoc`).

use axum::response::Html;
use axum::routing::get;
use axum::{Json, Router};
use serde_json::{json, Map, Value};

use crate::core::config::Settings;

const SCALAR_OAUTH2_SCHEME: &str = "OAuth2PasswordBearer";

fn schema_ref(name: &str) -> Value {
    json!({ "$ref": format!("#/components/schemas/{}", name) })
}

fn json_content(schema: Value) -> Value {
    json!({ "application/json": { "schema": schema } })
}

struct Op<'a> {
    path: &'a str,
    method: &'a str,
    tag: &'a str,
    summary: &'a str,
    secured: bool,
    request: Option<Value>,
    form: bool,
    status: &'a str,
    response: Option<Value>,
}

fn add_op(paths: &mut Map<String, Value>, op: Op) {
    let mut operation = Map::new();
    operation.insert("tags".to_string(), json!([op.tag]));
    operation.insert("summary".to_string(), json!(op.summary));

    let mut params: Vec<Value> = Vec::new();
    if op.path.contains("{id}") {
        params.push(json!({
            "name": "id", "in": "path", "required": true,
            "schema": { "type": "string", "format": "uuid" }
        }));
    }
    if !params.is_empty() {
        operation.insert("parameters".to_string(), Value::Array(params));
    }

    if op.secured {
        operation.insert(
            "security".to_string(),
            json!([{ (SCALAR_OAUTH2_SCHEME): [] }]),
        );
    }
    if let Some(schema) = op.request {
        operation.insert(
            "requestBody".to_string(),
            json!({ "required": true, "content": json_content(schema) }),
        );
    }
    if op.form {
        operation.insert(
            "requestBody".to_string(),
            json!({
                "required": true,
                "content": { "application/x-www-form-urlencoded": { "schema": {
                    "type": "object",
                    "required": ["username", "password"],
                    "properties": {
                        "username": { "type": "string" },
                        "password": { "type": "string", "format": "password" }
                    }
                } } }
            }),
        );
    }

    let mut ok = Map::new();
    ok.insert("description".to_string(), json!("Successful Response"));
    if let Some(schema) = op.response {
        ok.insert("content".to_string(), json_content(schema));
    }
    operation.insert(
        "responses".to_string(),
        json!({
            (op.status): Value::Object(ok),
            "4XX": { "description": "Error", "content": json_content(schema_ref("Detail")) }
        }),
    );

    let entry = paths
        .entry(op.path.to_string())
        .or_insert_with(|| Value::Object(Map::new()));
    if let Value::Object(methods) = entry {
        methods.insert(op.method.to_string(), Value::Object(operation));
    }
}

fn simple<'a>(path: &'a str, method: &'a str, tag: &'a str, summary: &'a str) -> Op<'a> {
    Op {
        path,
        method,
        tag,
        summary,
        secured: false,
        request: None,
        form: false,
        status: "200",
        response: None,
    }
}

fn components(token_url: &str) -> Value {
    json!({
        "securitySchemes": {
            (SCALAR_OAUTH2_SCHEME): {
                "type": "oauth2",
                "flows": { "password": { "tokenUrl": token_url, "scopes": {} } }
            }
        },
        "schemas": {
            "Detail": { "type": "object", "properties": { "detail": { "type": "string" } } },
            "Message": { "type": "object", "required": ["message"],
                "properties": { "message": { "type": "string" } } },
            "Token": { "type": "object", "required": ["access_token", "token_type"],
                "properties": { "access_token": { "type": "string" },
                                "token_type": { "type": "string" } } },
            "UserPublic": { "type": "object",
                "required": ["id", "email", "is_active", "is_superuser"],
                "properties": {
                    "id": { "type": "string", "format": "uuid" },
                    "email": { "type": "string" },
                    "is_active": { "type": "boolean" },
                    "is_superuser": { "type": "boolean" },
                    "full_name": { "type": ["string", "null"] } } },
            "UsersPublic": { "type": "object", "required": ["data", "count"],
                "properties": {
                    "data": { "type": "array", "items": schema_ref("UserPublic") },
                    "count": { "type": "integer" } } },
            "UserCreate": { "type": "object", "required": ["email", "password"],
                "properties": {
                    "email": { "type": "string", "maxLength": 255 },
                    "password": { "type": "string", "minLength": 8, "maxLength": 128 },
                    "is_active": { "type": "boolean", "default": true },
                    "is_superuser": { "type": "boolean", "default": false },
                    "full_name": { "type": ["string", "null"], "maxLength": 255 } } },
            "UserUpdate": { "type": "object",
                "properties": {
                    "email": { "type": "string", "maxLength": 255 },
                    "password": { "type": "string", "minLength": 8, "maxLength": 128 },
                    "is_active": { "type": "boolean" },
                    "is_superuser": { "type": "boolean" },
                    "full_name": { "type": ["string", "null"], "maxLength": 255 } } },
            "PrivateUserCreate": { "type": "object", "required": ["email", "password"],
                "properties": {
                    "email": { "type": "string", "maxLength": 255 },
                    "password": { "type": "string", "minLength": 8, "maxLength": 128 },
                    "full_name": { "type": ["string", "null"], "maxLength": 255 } } },
            "NoteCreate": { "type": "object", "required": ["title"],
                "properties": {
                    "title": { "type": "string", "minLength": 1, "maxLength": 255 },
                    "content": { "type": "string", "maxLength": 10000, "default": "" } } },
            "NoteUpdate": { "type": "object",
                "properties": {
                    "title": { "type": "string", "minLength": 1, "maxLength": 255 },
                    "content": { "type": "string", "maxLength": 10000 } } },
            "NotePublic": { "type": "object",
                "required": ["id", "title", "content", "owner_id", "created_at", "updated_at"],
                "properties": {
                    "id": { "type": "string", "format": "uuid" },
                    "title": { "type": "string" },
                    "content": { "type": "string" },
                    "owner_id": { "type": "string", "format": "uuid" },
                    "created_at": { "type": "string", "format": "date-time" },
                    "updated_at": { "type": "string", "format": "date-time" } } }
        }
    })
}

/// Build the OpenAPI 3.1 document for the routes this server exposes.
pub fn build_spec(settings: &Settings) -> Value {
    let auth = "[BASE] Auth";
    let users = "[SUPERADMIN] Core - User Management";
    let sample = "[APPS] Sample";
    let utils = "[SYSTEM] System - Utils";
    let private = "[SYSTEM] System - Private";

    let mut paths: Map<String, Value> = Map::new();

    add_op(
        &mut paths,
        simple("/utils/health-check", "get", utils, "Health Check"),
    );
    if settings.is_local() {
        add_op(
            &mut paths,
            Op {
                response: Some(schema_ref("Message")),
                ..simple("/private/ping", "get", private, "Private Ping")
            },
        );
        add_op(
            &mut paths,
            Op {
                request: Some(schema_ref("PrivateUserCreate")),
                response: Some(schema_ref("UserPublic")),
                ..simple("/private/users", "post", private, "Create User (local)")
            },
        );
        add_op(
            &mut paths,
            simple("/private/jobs/ping", "post", private, "Enqueue Ping Job"),
        );
    }

    add_op(
        &mut paths,
        Op {
            form: true,
            response: Some(schema_ref("Token")),
            ..simple("/base/login/access-token", "post", auth, "Login Access Token")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            response: Some(schema_ref("UserPublic")),
            ..simple("/base/login/me", "get", auth, "Read Users Me")
        },
    );

    add_op(
        &mut paths,
        Op {
            secured: true,
            response: Some(schema_ref("UsersPublic")),
            ..simple("/base/users/admin", "get", users, "Read Users")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            request: Some(schema_ref("UserCreate")),
            response: Some(schema_ref("UserPublic")),
            ..simple("/base/users/admin", "post", users, "Create User")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            response: Some(schema_ref("UserPublic")),
            ..simple("/base/users/{id}/admin", "get", users, "Read User By Id")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            request: Some(schema_ref("UserUpdate")),
            response: Some(schema_ref("UserPublic")),
            ..simple("/base/users/{id}/admin", "patch", users, "Update User")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            response: Some(schema_ref("Message")),
            ..simple("/base/users/{id}/admin", "delete", users, "Delete User")
        },
    );

    add_op(
        &mut paths,
        Op {
            response: Some(schema_ref("Message")),
            ..simple("/sample", "get", sample, "Sample Root")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            response: Some(json!({ "type": "array", "items": schema_ref("NotePublic") })),
            ..simple("/sample/notes", "get", sample, "List Notes")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            request: Some(schema_ref("NoteCreate")),
            status: "201",
            response: Some(schema_ref("NotePublic")),
            ..simple("/sample/notes", "post", sample, "Create Note")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            response: Some(schema_ref("NotePublic")),
            ..simple("/sample/notes/{id}", "get", sample, "Read Note")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            request: Some(schema_ref("NoteUpdate")),
            response: Some(schema_ref("NotePublic")),
            ..simple("/sample/notes/{id}", "patch", sample, "Update Note")
        },
    );
    add_op(
        &mut paths,
        Op {
            secured: true,
            status: "204",
            ..simple("/sample/notes/{id}", "delete", sample, "Delete Note")
        },
    );

    let token_url = format!("{}/base/login/access-token", settings.api_v1_str);
    json!({
        "openapi": "3.1.0",
        "info": { "title": settings.project_name, "version": "0.1.0" },
        "servers": [{ "url": settings.api_v1_str }],
        "paths": Value::Object(paths),
        "components": components(&token_url)
    })
}

fn swagger_html(title: &str, spec_url: &str) -> String {
    format!(
        r##"<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title} - Swagger UI</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
window.ui = SwaggerUIBundle({{ url: "{spec_url}", dom_id: "#swagger-ui", persistAuthorization: true }});
</script>
</body>
</html>"##,
        title = title,
        spec_url = spec_url
    )
}

fn scalar_html(title: &str, spec_url: &str) -> String {
    let configuration = json!({
        "theme": "elysiajs",
        "layout": "modern",
        "persistAuth": true,
        "authentication": { "preferredSecurityScheme": SCALAR_OAUTH2_SCHEME }
    })
    .to_string();
    format!(
        r##"<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title} - Scalar</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
<script id="api-reference" data-url="{spec_url}" data-configuration='{configuration}'></script>
<script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>"##,
        title = title,
        spec_url = spec_url,
        configuration = configuration
    )
}

/// `/docs`, `/sdoc` and `<api prefix>/openapi.json`.
pub fn router<S>(settings: &Settings) -> Router<S>
where
    S: Clone + Send + Sync + 'static,
{
    let spec_url = format!("{}/openapi.json", settings.api_v1_str);
    let spec = build_spec(settings);
    let swagger = swagger_html(&settings.project_name, &spec_url);
    let scalar = scalar_html(&settings.project_name, &spec_url);

    Router::new()
        .route(
            "/docs",
            get(move || {
                let page = swagger.clone();
                async move { Html(page) }
            }),
        )
        .route(
            "/sdoc",
            get(move || {
                let page = scalar.clone();
                async move { Html(page) }
            }),
        )
        .route(
            &spec_url,
            get(move || {
                let doc = spec.clone();
                async move { Json(doc) }
            }),
        )
}
