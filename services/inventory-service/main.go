package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"net/http"
	"os"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
)

var tracer trace.Tracer

func main() {
	ctx := context.Background()

	shutdown, err := initTracer(ctx)
	if err != nil {
		slog.Error("failed to initialize tracer", "error", err)
		os.Exit(1)
	}
	defer shutdown(ctx)

	tracer = otel.Tracer("inventory-service")

	mux := http.NewServeMux()
	mux.HandleFunc("POST /check", handleCheck)
	mux.HandleFunc("GET /health", handleHealth)

	handler := otelhttp.NewHandler(mux, "inventory-service")

	addr := ":8082"
	slog.Info("inventory-service starting", "addr", addr)
	if err := http.ListenAndServe(addr, handler); err != nil {
		slog.Error("server failed", "error", err)
		os.Exit(1)
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"healthy","service":"inventory-service"}`))
}

func handleCheck(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	span := trace.SpanFromContext(ctx)
	traceID := span.SpanContext().TraceID().String()

	logger := slog.With("trace_id", traceID, "service", "inventory-service")

	var req struct {
		OrderID string        `json:"order_id"`
		Items   []interface{} `json:"items"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		logger.Error("invalid request body", "error", err.Error())
		http.Error(w, `{"error":"invalid request"}`, http.StatusBadRequest)
		return
	}

	span.SetAttributes(
		attribute.String("order.id", req.OrderID),
		attribute.Int("inventory.item_count", len(req.Items)),
	)

	logger.Info("checking inventory",
		"order_id", req.OrderID,
		"item_count", len(req.Items),
	)

	// Simulate stock check with small random delay (50-200ms)
	delay := time.Duration(50+rand.Intn(150)) * time.Millisecond
	time.Sleep(delay)

	span.SetAttributes(attribute.Bool("inventory.in_stock", true))

	logger.Info("inventory check passed",
		"order_id", req.OrderID,
		"delay_ms", delay.Milliseconds(),
	)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"order_id": req.OrderID,
		"in_stock": true,
		"message":  "All items available",
	})
}

func initTracer(ctx context.Context) (func(context.Context) error, error) {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4317"
	}

	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(endpoint),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		return nil, fmt.Errorf("creating OTLP exporter: %w", err)
	}

	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceName("inventory-service"),
			semconv.ServiceVersion("1.0.0"),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("creating resource: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	return tp.Shutdown, nil
}
