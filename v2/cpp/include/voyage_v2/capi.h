#pragma once
/* C interface of the voyage_v2 core, used from Python through ctypes.
 * v2_arc_cost returns 9999 mt when the SOG needs an SWS outside 2-25 kn.
 * Every function catches C++ exceptions: on failure it returns NULL, NaN or a
 * nonzero status, and v2_last_error() says why. Steps are 15-minute steps from
 * the voyage start; a negative tau means pseudo real-time (tau = t). */

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    double length_m, displacement_t, block_coefficient, fcr_coefficient;
} v2_ship;

typedef struct {
    double wind_speed_kmh, wind_from_deg, current_speed_kmh, current_to_deg;
} v2_conditions;

typedef struct {
    v2_conditions conditions;
    int beaufort;
    double sws_kn, hours, fcr_mt_h, fuel_mt;
    int feasible;                       /* 1 when sws_kn lies in the vessel's SWS range */
    int wind_run, current_run;          /* index of the source run, in order of run start */
    int wind_held, current_held;        /* 1 when the latest value before t was held */
} v2_arc_info;

typedef struct v2_archive v2_archive;
typedef struct v2_voyage v2_voyage;

const char* v2_last_error(void);

/* grid 0 = wind (direction "from"), 1 = current (direction "to"); values per [cell][hour] */
v2_archive* v2_archive_new(int n_wind_cells, int n_current_cells);
int v2_archive_add_run(v2_archive* archive, int grid, int init_step, int first_step, int n_hours,
                       const float* speed_kmh, const float* direction_deg);
void v2_archive_free(v2_archive* archive);

/* Copies the archive; the caller still frees it. */
v2_voyage* v2_voyage_new(const v2_ship* ship, int n_subsegments, const double* length_nm,
                         const double* bearing_deg, const int* wind_cell, const int* current_cell,
                         int eta_steps, const v2_archive* archive);
void v2_voyage_free(v2_voyage* voyage);

double v2_arc_cost(const v2_voyage* voyage, int sub, double sog_kn, int t, int tau);
int v2_arc_costs(const v2_voyage* voyage, long n, const int* sub, const double* sog_kn,
                 const int* t, const int* tau, double* out);
int v2_arc_detail(const v2_voyage* voyage, int sub, double sog_kn, int t, int tau,
                  v2_arc_info* out);

/* Minimum-fuel plan on the full time-distance graph (see dp.hpp) */
typedef struct {
    double sog_band_kn;
    int tick_s;
    double zeta_m;
    double merge_nm;
    int forecast;                       /* 0: pseudo real-time; 1: forecast known at the start */
} v2_dp_options;

typedef struct {
    int feasible;
    double fuel_mt, arrival_h, constant_sog_fuel_mt, v_min_kn, v_max_kn;
    int n_segments, path_length;
    long long nodes, distance_line_nodes, time_line_nodes, reached_nodes;
    long long arcs, infeasible_arcs, sws_evaluations;
    double setup_s, sweep_s, memory_mb;
} v2_dp_summary;

typedef struct v2_dp_result v2_dp_result;

v2_dp_result* v2_dp_solve(const v2_voyage* voyage, const v2_dp_options* options);
void v2_dp_summary_of(const v2_dp_result* result, v2_dp_summary* out);
/* arrays of length path_length */
void v2_dp_path(const v2_dp_result* result, double* t0_h, double* d0_nm, double* t1_h, double* d1_nm,
                double* sog_kn, double* sws_kn, double* fuel_mt, int* segment, int* step);
/* arrays of length n_segments */
void v2_dp_segments(const v2_dp_result* result, double* start_nm, double* length_nm, double* bearing_deg,
                    int* first_sub, int* n_subs, int* dominant_sub);
void v2_dp_free(v2_dp_result* result);

/* Luo et al. multistage DP (see luo.hpp); its result is read with the v2_dp_* functions */
typedef struct {
    double sog_band_kn;
    int epoch_steps;                    /* decision epoch in 0.25 h steps (24 = 6 h) */
    double dist_step_nm;                /* node spacing on the epoch lines; 0 = 0.1 kn x epoch length */
    int forecast;
} v2_luo_options;

v2_dp_result* v2_luo_solve(const v2_voyage* voyage, const v2_luo_options* options);

/* The speed and fuel model on its own */
int v2_beaufort_number(double wind_speed_kmh);
double v2_sog_from_sws(const v2_ship* ship, double sws_kn, double bearing_deg, const v2_conditions* c);
double v2_sws_from_sog(const v2_ship* ship, double sog_kn, double bearing_deg, const v2_conditions* c);
double v2_fcr_from_sog(const v2_ship* ship, double sog_kn, double bearing_deg, const v2_conditions* c);

#ifdef __cplusplus
}
#endif
