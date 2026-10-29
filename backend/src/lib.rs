//! FoxG Rust/Axum backend library. The `api` and `worker` binaries and the
//! integration tests in `../tests/backend` all use this crate.
#![recursion_limit = "256"]

pub mod core;
pub mod modules;

use aide::axum::ApiRouter;
use axum::http::HeaderValue;
use axum::Router;
use tower_http::cors::{AllowHeaders, AllowMethods, AllowOrigin, CorsLayer};
use tower_http::trace::{DefaultMakeSpan, DefaultOnResponse, TraceLayer};
use tower_http::LatencyUnit;
use tracing::Level;

use crate::core::config::Settings;
use crate::core::error::ApiError;
use crate::core::state::AppState;

async fn not_found() -> ApiError {
    ApiError::not_found("Not Found")
}

fn cors_layer(settings: &Settings) -> CorsLayer {
    let origins: Vec<HeaderValue> = settings
        .all_cors_origins()
        .iter()
        .filter_map(|o| HeaderValue::from_str(o).ok())
        .collect();
    CorsLayer::new()
        .allow_origin(AllowOrigin::list(origins))
        .allow_credentials(true)
        .allow_methods(AllowMethods::mirror_request())
        .allow_headers(AllowHeaders::mirror_request())
}

/// Build the full application router from a prepared [`AppState`].
pub fn build_router(state: AppState) -> Router {
    let settings = state.config.clone();

    // Every route is documented from its handler (core::api); the spec is never hand-written.
    let api: ApiRouter<AppState> = ApiRouter::new()
        .merge(modules::system::router::router(&settings))
        .merge(modules::base::router())
        .merge(modules::apps::router());
    let (api, doc) = crate::core::openapi::finish(api, &settings);

    let prefix = settings.api_v1_str.clone();
    let app: Router<AppState> = Router::new()
        .nest(&prefix, api)
        .merge(crate::core::openapi::router::<AppState>(&settings, doc))
        .fallback(not_found);

    app.layer(cors_layer(&settings))
        .layer(access_log_layer())
        .with_state(state)
}

/// One INFO line per request: method, path, status, latency (like uvicorn's access log).
/// Quiet it with `RUST_LOG=info,tower_http=warn`.
fn access_log_layer() -> TraceLayer<
    tower_http::classify::SharedClassifier<tower_http::classify::ServerErrorsAsFailures>,
> {
    TraceLayer::new_for_http()
        .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
        .on_response(DefaultOnResponse::new().level(Level::INFO).latency_unit(LatencyUnit::Millis))
}
