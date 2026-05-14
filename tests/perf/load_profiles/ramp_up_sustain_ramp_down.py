import math

from locust import LoadTestShape


class RampUpSustainRampDown(LoadTestShape):
    @staticmethod
    def _spawn_rate(start_users: int, end_users: int, duration_seconds: int) -> int:
        user_delta = abs(end_users - start_users)
        if user_delta == 0:
            return 1
        if duration_seconds <= 0:
            return max(1, user_delta)
        return max(1, math.ceil(user_delta / duration_seconds))

    def _shape_options(self) -> tuple[int, int, int, int, int, int]:
        options = self.runner.environment.parsed_options
        return (
            max(0, int(options.ramp_up_users)),
            max(0, int(options.ramp_up_duration)),
            max(0, int(options.sustain_users)),
            max(0, int(options.sustain_duration)),
            max(0, int(options.ramp_down_users)),
            max(0, int(options.ramp_down_duration)),
        )

    def tick(self):
        run_time = self.get_run_time()
        (
            ramp_up_users,
            ramp_up_duration,
            sustain_users,
            sustain_duration,
            ramp_down_users,
            ramp_down_duration,
        ) = self._shape_options()

        ramp_up_end = ramp_up_duration
        sustain_end = ramp_up_end + sustain_duration
        ramp_down_end = sustain_end + ramp_down_duration

        if run_time < ramp_up_end:
            return (
                ramp_up_users,
                self._spawn_rate(0, ramp_up_users, ramp_up_duration),
            )

        if run_time < sustain_end:
            return (
                sustain_users,
                self._spawn_rate(ramp_up_users, sustain_users, 1),
            )

        if run_time < ramp_down_end:
            return (
                ramp_down_users,
                self._spawn_rate(
                    sustain_users,
                    ramp_down_users,
                    ramp_down_duration,
                ),
            )

        return None
