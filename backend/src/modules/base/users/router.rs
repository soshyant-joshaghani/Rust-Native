use axum::body::Bytes;
use axum::extract::{Path, RawQuery, State};
use axum::http::HeaderMap;
use axum::routing::get;
use axum::{Json, Router};
use serde::Deserialize;

use crate::core::error::{parse_json, parse_query, parse_uuid, ApiResult};
use crate::core::state::AppState;
use crate::modules::base::auth::{current_user, current_superuser};
use crate::modules::base::users::schemas::{
    Message, UserCreate, UserPublic, UserUpdate, UsersPublic,
};
use crate::modules::base::users::service::UserService;

#[derive(Debug, Default, Deserialize)]
struct Pagination {
    skip: Option<i64>,
    limit: Option<i64>,
}

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/users/admin", get(read_users).post(create_user))
        .route(
            "/users/{id}/admin",
            get(read_user).patch(update_user).delete(delete_user),
        )
}

async fn read_users(
    State(state): State<AppState>,
    headers: HeaderMap,
    RawQuery(raw): RawQuery,
) -> ApiResult<Json<UsersPublic>> {
    current_superuser(&state, &headers).await?;
    let page: Pagination = parse_query(&raw)?;
    let skip = page.skip.unwrap_or(0).max(0);
    let limit = page.limit.unwrap_or(100).max(0);
    let result = UserService::new(&state).list(skip, limit).await?;
    Ok(Json(result))
}

async fn create_user(
    State(state): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> ApiResult<Json<UserPublic>> {
    current_superuser(&state, &headers).await?;
    let input: UserCreate = parse_json(&body)?;
    let user = UserService::new(&state).create(input).await?;
    Ok(Json(UserPublic::from(&user)))
}

async fn read_user(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> ApiResult<Json<UserPublic>> {
    let current = current_user(&state, &headers).await?;
    let id = parse_uuid(&id)?;
    let user = UserService::new(&state).get_for(&current, id).await?;
    Ok(Json(UserPublic::from(&user)))
}

async fn update_user(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
    body: Bytes,
) -> ApiResult<Json<UserPublic>> {
    current_superuser(&state, &headers).await?;
    let id = parse_uuid(&id)?;
    let input: UserUpdate = parse_json(&body)?;
    let user = UserService::new(&state).update(id, input).await?;
    Ok(Json(UserPublic::from(&user)))
}

async fn delete_user(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> ApiResult<Json<Message>> {
    let current = current_superuser(&state, &headers).await?;
    let id = parse_uuid(&id)?;
    UserService::new(&state).delete(&current, id).await?;
    Ok(Json(Message {
        message: "User deleted successfully".to_string(),
    }))
}
