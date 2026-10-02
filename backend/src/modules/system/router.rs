use axum::body::Bytes;
use axum::extract::{RawQuery, State};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;
use serde_json::{json, Value};

use crate::core::config::Settings;
use crate::core::error::{check_email, check_len, parse_json, parse_query, ApiError, ApiResult};
use crate::core::state::AppState;
use crate::modules::base::users::schemas::{Message, UserCreate, UserPublic};
use crate::modules::base::users::service::UserService;

/// `/utils/*` always; `/private/*` only when `ENVIRONMENT=local`.
pub fn router(settings: &Settings) -> Router<AppState> {
    let mut routes: Router<AppState> =
        Router::new().route("/utils/health-check", get(health_check));
    if settings.is_local() {
        routes = routes
            .route("/private/ping", get(private_ping))
            .route("/private/users", post(private_create_user))
            .route("/private/jobs/ping", post(enqueue_ping_job));
    }
    routes
}

async fn health_check() -> Json<bool> {
    Json(true)
}

async fn private_ping() -> Json<Message> {
    Json(Message {
        message: "private ok".to_string(),
    })
}

#[derive(Debug, Deserialize)]
struct PrivateUserCreate {
    email: String,
    password: String,
    #[serde(default)]
    full_name: Option<String>,
}

async fn private_create_user(
    State(state): State<AppState>,
    body: Bytes,
) -> ApiResult<Json<UserPublic>> {
    let input: PrivateUserCreate = parse_json(&body)?;
    check_email("email", &input.email)?;
    check_len("password", &input.password, 8, 128)?;
    let create = UserCreate {
        email: input.email,
        password: input.password,
        is_active: true,
        is_superuser: false,
        full_name: input.full_name,
    };
    let user = UserService::new(&state).create(create).await?;
    Ok(Json(UserPublic::from(&user)))
}

#[derive(Debug, Default, Deserialize)]
struct PingQuery {
    message: Option<String>,
}

async fn enqueue_ping_job(
    State(state): State<AppState>,
    RawQuery(raw): RawQuery,
) -> ApiResult<Json<Value>> {
    let query: PingQuery = parse_query(&raw)?;
    let message = query.message.unwrap_or_else(|| "ping".to_string());
    let args = json!({ "message": message });
    match state.jobs.enqueue("ping", args).await {
        Ok(job_id) => Ok(Json(json!({ "job_id": job_id, "message": message }))),
        Err(err) => Err(ApiError::unavailable(format!("Redis unavailable: {}", err))),
    }
}
