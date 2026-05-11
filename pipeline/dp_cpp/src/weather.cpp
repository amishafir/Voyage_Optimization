#include "weather.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <set>
#include <hdf5.h>

// ---- HDF5 field-reading helpers ----

static std::vector<int64_t> h5_read_int_field(hid_t dset, hsize_t n_rows,
                                                const char* field) {
    hid_t mem = H5Tcreate(H5T_COMPOUND, sizeof(int64_t));
    H5Tinsert(mem, field, 0, H5T_NATIVE_INT64);
    std::vector<int64_t> buf(n_rows);
    H5Dread(dset, mem, H5S_ALL, H5S_ALL, H5P_DEFAULT, buf.data());
    H5Tclose(mem);
    return buf;
}

static std::vector<double> h5_read_double_field(hid_t dset, hsize_t n_rows,
                                                  const char* field) {
    hid_t mem = H5Tcreate(H5T_COMPOUND, sizeof(double));
    H5Tinsert(mem, field, 0, H5T_NATIVE_DOUBLE);
    std::vector<double> buf(n_rows);
    H5Dread(dset, mem, H5S_ALL, H5S_ALL, H5P_DEFAULT, buf.data());
    H5Tclose(mem);
    return buf;
}

static hsize_t h5_dataset_rows(hid_t dset) {
    hid_t space = H5Dget_space(dset);
    hsize_t dims[2] = {0, 0};
    H5Sget_simple_extent_dims(space, dims, nullptr);
    H5Sclose(space);
    return dims[0];
}

// ---- VoyageWeather constructor ----

VoyageWeather::VoyageWeather(const std::string& h5_path) {
    hid_t fid = H5Fopen(h5_path.c_str(), H5F_ACC_RDONLY, H5P_DEFAULT);
    if (fid < 0) throw std::runtime_error("Cannot open HDF5: " + h5_path);

    // --- metadata ---
    {
        hid_t ds = H5Dopen2(fid, "metadata", H5P_DEFAULT);
        hsize_t n = h5_dataset_rows(ds);
        auto node_ids = h5_read_int_field(ds, n, "node_id");
        auto dists    = h5_read_double_field(ds, n, "distance_from_start_nm");
        auto lats     = h5_read_double_field(ds, n, "lat");
        auto lons     = h5_read_double_field(ds, n, "lon");
        auto segs     = h5_read_int_field(ds, n, "segment");
        H5Dclose(ds);
        waypoints_.reserve(n);
        for (hsize_t i = 0; i < n; ++i)
            waypoints_.push_back({lats[i], lons[i], (int)node_ids[i], dists[i], (int)segs[i]});
        std::sort(waypoints_.begin(), waypoints_.end(),
                  [](const H5Waypoint& a, const H5Waypoint& b) {
                      return a.distance_nm < b.distance_nm; });
        distances_.reserve(waypoints_.size());
        for (auto& wp : waypoints_) {
            distances_.push_back(wp.distance_nm);
            wps_by_seg_[wp.segment].push_back(wp);
        }
        std::set<int> seg_set;
        for (auto& wp : waypoints_) seg_set.insert(wp.segment);
        segments_in_order_ = std::vector<int>(seg_set.begin(), seg_set.end());
    }

    // --- actual_weather ---
    {
        hid_t ds = H5Dopen2(fid, "actual_weather", H5P_DEFAULT);
        hsize_t n = h5_dataset_rows(ds);
        auto node_ids    = h5_read_int_field(ds, n, "node_id");
        auto s_hours     = h5_read_int_field(ds, n, "sample_hour");
        auto wind_sp     = h5_read_double_field(ds, n, "wind_speed_10m_kmh");
        auto wind_dir    = h5_read_double_field(ds, n, "wind_direction_10m_deg");
        auto bn_d        = h5_read_double_field(ds, n, "beaufort_number");
        auto wave        = h5_read_double_field(ds, n, "wave_height_m");
        auto cur_sp      = h5_read_double_field(ds, n, "ocean_current_velocity_kmh");
        auto cur_dir     = h5_read_double_field(ds, n, "ocean_current_direction_deg");
        H5Dclose(ds);
        std::set<int> sh_set;
        for (hsize_t i = 0; i < n; ++i) {
            int ni = (int)node_ids[i]; int sh = (int)s_hours[i];
            actual_[{ni, sh}] = {wind_sp[i], wind_dir[i], (int)std::round(bn_d[i]),
                                  wave[i], cur_sp[i], cur_dir[i]};
            sh_set.insert(sh);
        }
        sample_hours_ = std::vector<int>(sh_set.begin(), sh_set.end());
    }

    // --- predicted_weather ---
    {
        hid_t ds = H5Dopen2(fid, "predicted_weather", H5P_DEFAULT);
        hsize_t n = h5_dataset_rows(ds);
        auto node_ids    = h5_read_int_field(ds, n, "node_id");
        auto f_hours     = h5_read_int_field(ds, n, "forecast_hour");
        auto s_hours     = h5_read_int_field(ds, n, "sample_hour");
        auto wind_sp     = h5_read_double_field(ds, n, "wind_speed_10m_kmh");
        auto wind_dir    = h5_read_double_field(ds, n, "wind_direction_10m_deg");
        auto bn_d        = h5_read_double_field(ds, n, "beaufort_number");
        auto wave        = h5_read_double_field(ds, n, "wave_height_m");
        auto cur_sp      = h5_read_double_field(ds, n, "ocean_current_velocity_kmh");
        auto cur_dir     = h5_read_double_field(ds, n, "ocean_current_direction_deg");
        H5Dclose(ds);
        std::set<int> fh_set;
        for (hsize_t i = 0; i < n; ++i) {
            int ni = (int)node_ids[i]; int fh = (int)f_hours[i]; int sh = (int)s_hours[i];
            predicted_[{ni, fh, sh}] = {wind_sp[i], wind_dir[i], (int)std::round(bn_d[i]),
                                         wave[i], cur_sp[i], cur_dir[i]};
            fh_set.insert(fh);
        }
        forecast_hours_ = std::vector<int>(fh_set.begin(), fh_set.end());
    }

    // Read route_name attribute if present
    if (H5Aexists(fid, "route_name") > 0) {
        hid_t attr = H5Aopen(fid, "route_name", H5P_DEFAULT);
        hid_t atype = H5Aget_type(attr);
        hsize_t sz = H5Tget_size(atype);
        std::string buf(sz + 1, '\0');
        H5Aread(attr, atype, buf.data());
        route_name_ = buf.c_str();
        H5Tclose(atype); H5Aclose(attr);
    }
    H5Fclose(fid);
}

// ---- Internal helpers ----

const VoyageWeather::WeatherRow* VoyageWeather::row_for(int node_id, int sample_hour,
                                                          int forecast_hour) const {
    if (forecast_hour < 0) {
        auto it = actual_.find({node_id, sample_hour});
        return it != actual_.end() ? &it->second : nullptr;
    }
    auto it = predicted_.find({node_id, forecast_hour, sample_hour});
    return it != predicted_.end() ? &it->second : nullptr;
}

const H5Waypoint& VoyageWeather::nearest_waypoint(double d) const {
    double d_cl = std::max(0.0, std::min(d, distances_.back()));
    auto it = std::lower_bound(distances_.begin(), distances_.end(), d_cl);
    if (it == distances_.begin()) return waypoints_.front();
    if (it == distances_.end())   return waypoints_.back();
    size_t i = it - distances_.begin();
    if (std::abs(distances_[i-1] - d_cl) <= std::abs(distances_[i] - d_cl))
        return waypoints_[i-1];
    return waypoints_[i];
}

int VoyageWeather::segment_for_distance(double d) const {
    auto bounds = segment_boundaries_nm();
    int first_seg = waypoints_.front().segment;
    // bisect_right equivalent
    int idx = (int)(std::upper_bound(bounds.begin(), bounds.end(), d) - bounds.begin());
    return first_seg + idx;
}

const H5Waypoint& VoyageWeather::nearest_valid_in_segment(double d, int seg,
                                                            int sample_hour,
                                                            int forecast_hour) const {
    // Try valid waypoints in segment first
    auto sit = wps_by_seg_.find(seg);
    if (sit != wps_by_seg_.end()) {
        const H5Waypoint* best = nullptr;
        double best_dist = 1e18;
        for (auto& wp : sit->second) {
            auto* row = row_for(wp.node_id, sample_hour, forecast_hour);
            if (!row_has_nan(row)) {
                double dd = std::abs(wp.distance_nm - d);
                if (dd < best_dist) { best_dist = dd; best = &wp; }
            }
        }
        if (best) return *best;
    }
    // Fall back to any valid waypoint on the route
    const H5Waypoint* best = nullptr;
    double best_dist = 1e18;
    for (auto& wp : waypoints_) {
        auto* row = row_for(wp.node_id, sample_hour, forecast_hour);
        if (!row_has_nan(row)) {
            double dd = std::abs(wp.distance_nm - d);
            if (dd < best_dist) { best_dist = dd; best = &wp; }
        }
    }
    return best ? *best : nearest_waypoint(d);
}

WeatherDict VoyageWeather::row_to_dict(const WeatherRow& r) const {
    return {{"wind_speed_10m_kmh",       r.wind_speed_10m_kmh},
            {"wind_direction_10m_deg",   r.wind_direction_10m_deg},
            {"beaufort_number",          static_cast<double>(r.beaufort_number)},
            {"wave_height_m",            r.wave_height_m},
            {"ocean_current_velocity_kmh",   r.ocean_current_velocity_kmh},
            {"ocean_current_direction_deg",  r.ocean_current_direction_deg}};
}

// ---- Public lookups ----

WeatherDict VoyageWeather::weather_at(double d, int sample_hour, int forecast_hour) const {
    int seg = segment_for_distance(d);
    const auto& wp = nearest_valid_in_segment(d, seg, sample_hour, forecast_hour);
    const auto* row = row_for(wp.node_id, sample_hour, forecast_hour);
    if (!row) throw std::runtime_error("weather_at: no row found");
    auto dict = row_to_dict(*row);
    dict["beaufort_number"] = static_cast<double>(row->beaufort_number);
    return dict;
}

std::vector<double> VoyageWeather::segment_boundaries_nm() const {
    std::vector<double> out;
    int prev_seg = waypoints_.front().segment;
    for (size_t i = 1; i < waypoints_.size(); ++i) {
        if (waypoints_[i].segment != prev_seg) {
            out.push_back(waypoints_[i].distance_nm);
            prev_seg = waypoints_[i].segment;
        }
    }
    return out;
}

std::vector<double> VoyageWeather::weather_cell_boundaries_nm(double grid_deg) const {
    std::vector<double> out;
    if (waypoints_.empty()) return out;
    const auto& first = waypoints_.front();
    auto prev_cell = std::make_pair((int)std::floor(first.lat_deg / grid_deg),
                                    (int)std::floor(first.lon_deg / grid_deg));
    for (size_t i = 1; i < waypoints_.size(); ++i) {
        auto& w = waypoints_[i];
        auto cell = std::make_pair((int)std::floor(w.lat_deg / grid_deg),
                                   (int)std::floor(w.lon_deg / grid_deg));
        if (cell != prev_cell)
            out.push_back((waypoints_[i-1].distance_nm + w.distance_nm) / 2.0);
        prev_cell = cell;
    }
    return out;
}

// ---- Cell-canonical weather (Qg5b) ----

void VoyageWeather::build_cell_index(double grid_deg) const {
    int key = (int)std::round(grid_deg * 1000);
    if (cell_index_.count(key)) return;
    auto& idx = cell_index_[key];
    for (int i = 0; i < (int)waypoints_.size(); ++i) {
        CellKey c{(int)std::floor(waypoints_[i].lat_deg / grid_deg),
                  (int)std::floor(waypoints_[i].lon_deg / grid_deg)};
        idx[c].push_back(i);
    }
}

static double circular_mean_deg(const std::vector<double>& angles) {
    if (angles.empty()) return std::numeric_limits<double>::quiet_NaN();
    double sin_sum = 0, cos_sum = 0;
    for (double a : angles) {
        sin_sum += std::sin(a * M_PI / 180.0);
        cos_sum += std::cos(a * M_PI / 180.0);
    }
    double mean = std::atan2(sin_sum / angles.size(), cos_sum / angles.size()) * 180.0 / M_PI;
    return std::fmod(mean + 360.0, 360.0);
}

WeatherDict VoyageWeather::cell_weather(const CellKey& cell, int sample_hour,
                                          int forecast_hour, double grid_deg) const {
    WeatherCacheKey ck{cell.lat_idx, cell.lon_idx, sample_hour, forecast_hour};
    auto cit = cell_cache_.find(ck);
    if (cit != cell_cache_.end()) return cit->second;

    build_cell_index(grid_deg);
    int idx_key = (int)std::round(grid_deg * 1000);
    const auto& cell_idx = cell_index_.at(idx_key);
    auto wit = cell_idx.find(cell);

    WeatherDict result;
    if (wit == cell_idx.end() || wit->second.empty()) {
        for (const char* f : WEATHER_FIELDS)
            result[f] = std::numeric_limits<double>::quiet_NaN();
    } else {
        std::vector<double> wind_sp, wave, cur_sp, wind_dir, cur_dir, bns;
        for (int wi : wit->second) {
            const auto* row = row_for(waypoints_[wi].node_id, sample_hour, forecast_hour);
            if (row_has_nan(row)) continue;
            wind_sp.push_back(row->wind_speed_10m_kmh);
            wave.push_back(row->wave_height_m);
            cur_sp.push_back(row->ocean_current_velocity_kmh);
            wind_dir.push_back(row->wind_direction_10m_deg);
            cur_dir.push_back(row->ocean_current_direction_deg);
            bns.push_back(static_cast<double>(row->beaufort_number));
        }
        if (wind_sp.empty()) {
            for (const char* f : WEATHER_FIELDS)
                result[f] = std::numeric_limits<double>::quiet_NaN();
        } else {
            auto mean = [](const std::vector<double>& v) {
                double s = 0; for (double x : v) s += x; return s / v.size(); };
            result["wind_speed_10m_kmh"]          = mean(wind_sp);
            result["wind_direction_10m_deg"]       = circular_mean_deg(wind_dir);
            result["beaufort_number"]              = std::round(mean(bns));
            result["wave_height_m"]                = mean(wave);
            result["ocean_current_velocity_kmh"]   = mean(cur_sp);
            result["ocean_current_direction_deg"]  = circular_mean_deg(cur_dir);
        }
    }
    cell_cache_[ck] = result;
    return result;
}
