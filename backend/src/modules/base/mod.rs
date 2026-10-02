pub mod auth;
pub mod users;

use axum::Router;

use crate::core::state::AppState;

/// Routes under `/base`.
pub fn router() -> Router<AppState> {
    let routes: Router<AppState> = Router::new()
        .merge(auth::router::router())
        .merge(users::router::router());
    Router::new().nest("/base", routes)
}
