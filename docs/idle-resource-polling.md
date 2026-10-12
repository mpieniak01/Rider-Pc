# Idle resource reads

Rider-PC uses one refresh schedule per observation key. State and system data
are checked every 2 seconds, health every 5 seconds, and application/BUS metrics
every 10 seconds. Foreground state reads keep their short freshness budget.
Resource inventory is fetched on demand, not continuously in the background;
the same cache key and in-flight read serve all callers. Successful task/resource
actions invalidate those observations, including earlier requests still in flight.

The observed camera activity already present in Pi state/health determines
whether the background may request frames. OFF, unavailable and unknown stop
background frame downloads and vision polling. ON resumes vision polling.
An explicit metadata request still shows historical file information. Current
image requests with confirmed OFF return local 404; explicit archives continue
to reach Pi. Frame transfers are shared for 0.8 seconds by background, GET and
HEAD; source headers/times are preserved. Failed background transfers retry
after 5 seconds. These changes never start resources or issue actuator commands.

Pi shares resource ownership scans across status endpoints. Confirmed free
resources and failed probes are reused for 5 seconds; occupied resources for
3 seconds. Resource actions invalidate cached observations. Actual recovery
still obtains its direct current owner inspection before acting.


While camera is confirmed OFF, foreground metadata reads reuse the existing
historical snapshot without refreshing its source or receipt time. A cold cache
can perform one metadata read; resource actions clear it and observed ON resumes
normal fetching. Pi Overview also skips inactive vision polling.
