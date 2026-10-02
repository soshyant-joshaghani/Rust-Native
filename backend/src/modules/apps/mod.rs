pub mod sample;

use axum::Router;

use crate::core::state::AppState;

/// Add new app routers here.
pub fn router() -> Router<AppState> {
    Router::new().merge(sample::router::router())
}
