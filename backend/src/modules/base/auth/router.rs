use axum::body::Bytes;
use axum::extract::State;
use axum::http::HeaderMap;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use crate::core::error::{parse_form, ApiResult};
use crate::core::security;
use crate::core::state::AppState;
use crate::modules::base::auth::{current_user, Token};
use crate::modules::base::users::schemas::UserPublic;
use crate::modules::base::users::service::UserService;

#[derive(Debug, Deserialize)]
struct LoginForm {
    username: String,
    password: String,
}

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/login/access-token", post(login_access_token))
        .route("/login/me", get(read_me))
}

async fn login_access_token(
    State(state): State<AppState>,
    body: Bytes,
) -> ApiResult<Json<Token>> {
    let form: LoginForm = parse_form(&body)?;
    let user = UserService::new(&state)
        .authenticate(&form.username, &form.password)
        .await?;
    let token = security::create_access_token(
        &user.id.to_string(),
        &state.config.secret_key,
        state.config.access_token_expire_minutes,
    )
    .map_err(crate::core::error::ApiError::internal)?;
    Ok(Json(Token {
        access_token: token,
        token_type: "bearer".to_string(),
    }))
}

async fn read_me(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> ApiResult<Json<UserPublic>> {
    let user = current_user(&state, &headers).await?;
    Ok(Json(UserPublic::from(&user)))
}
