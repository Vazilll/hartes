#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define MAX_SENSORS 64
#define RING_BUFFER_SIZE 1024

typedef struct {
    int sensor_id;
    double current_val;
    double moving_avg;
    long sample_count;
} SensorState;

typedef struct {
    SensorState sensors[MAX_SENSORS];
    int active_sensor_count;
    double global_anomaly_threshold;
} TelemetryContext;

TelemetryContext* aegis_telemetry_init(double anomaly_threshold) {
    TelemetryContext* ctx = (TelemetryContext*)malloc(sizeof(TelemetryContext));
    if (!ctx) return NULL;
    memset(ctx, 0, sizeof(TelemetryContext));
    ctx->global_anomaly_threshold = anomaly_threshold > 0 ? anomaly_threshold : 3.0;
    return ctx;
}

int aegis_record_sample(TelemetryContext* ctx, int sensor_id, double val) {
    if (!ctx || sensor_id < 0 || sensor_id >= MAX_SENSORS) return -1;
    SensorState* s = &ctx->sensors[sensor_id];
    s->sensor_id = sensor_id;
    s->current_val = val;
    s->sample_count++;
    
    // Online Welford / moving average
    s->moving_avg += (val - s->moving_avg) / (double)s->sample_count;
    
    if (fabs(val - s->moving_avg) > ctx->global_anomaly_threshold) {
        return 1; // Anomaly detected
    }
    return 0; // Normal
}

void aegis_telemetry_free(TelemetryContext* ctx) {
    if (ctx) {
        free(ctx);
    }
}

int main(int argc, char** argv) {
    TelemetryContext* ctx = aegis_telemetry_init(2.5);
    int anomalies = 0;
    for (int i = 0; i < 50; i++) {
        double v = (i == 42) ? 100.0 : (double)(i % 5);
        if (aegis_record_sample(ctx, i % 8, v) == 1) {
            anomalies++;
        }
    }
    printf("Telemetry complete. Anomalies detected: %d\n", anomalies);
    aegis_telemetry_free(ctx);
    return 0;
}
