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

/* The speed and fuel model on its own */
int v2_beaufort_number(double wind_speed_kmh);
double v2_sog_from_sws(const v2_ship* ship, double sws_kn, double bearing_deg, const v2_conditions* c);
double v2_sws_from_sog(const v2_ship* ship, double sog_kn, double bearing_deg, const v2_conditions* c);
double v2_fcr_from_sog(const v2_ship* ship, double sog_kn, double bearing_deg, const v2_conditions* c);

#ifdef __cplusplus
}
#endif
