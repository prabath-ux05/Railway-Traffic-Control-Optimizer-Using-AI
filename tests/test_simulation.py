"""
tests/test_simulation.py
~~~~~~~~~~~~~~~~~~~~~~~~
Focused unit tests for Batch 3:
- SimulationClock (deterministic clock, step/advance, string parsing/formatting)
- SimulationEvent & EventQueue (deterministic discrete-event scheduling)
- TrainRuntimeState & SimulationState (in-memory state, transitions, delay, resource locking)
"""

import os
import unittest

from simulation.clock import SimulationClock, time_to_minutes, minutes_to_time_str
from simulation.events import EventType, SimulationEvent, EventQueue
from simulation.network import Network
from simulation.state import TrainStatus, TrainRuntimeState, SimulationState

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


class TestSimulationClock(unittest.TestCase):
    """Unit tests for SimulationClock and time conversions."""

    def test_time_conversions(self):
        self.assertEqual(time_to_minutes("00:00"), 0.0)
        self.assertEqual(time_to_minutes("05:30"), 330.0)
        self.assertEqual(time_to_minutes("05:30:30"), 330.5)
        self.assertEqual(time_to_minutes("23:59"), 1439.0)
        self.assertEqual(time_to_minutes(330), 330.0)

        self.assertEqual(minutes_to_time_str(0.0), "00:00")
        self.assertEqual(minutes_to_time_str(330.0), "05:30")
        self.assertEqual(minutes_to_time_str(330.5, include_seconds=True), "05:30:30")
        self.assertEqual(minutes_to_time_str(1439.0), "23:59")

    def test_invalid_time_strings_raise(self):
        with self.assertRaises(ValueError):
            time_to_minutes("25:00")
        with self.assertRaises(ValueError):
            time_to_minutes("05:60")
        with self.assertRaises(ValueError):
            time_to_minutes("invalid")
        with self.assertRaises(TypeError):
            time_to_minutes(None)

    def test_clock_initialization(self):
        clock = SimulationClock(start_time="05:00", step_size_minutes=2.0)
        self.assertEqual(clock.start_time, 300.0)
        self.assertEqual(clock.current_time, 300.0)
        self.assertEqual(clock.step_size, 2.0)
        self.assertEqual(clock.tick_count, 0)
        self.assertEqual(clock.elapsed_minutes, 0.0)
        self.assertEqual(clock.current_time_str, "05:00")

    def test_clock_tick(self):
        clock = SimulationClock(start_time="06:00", step_size_minutes=1.5)
        t1 = clock.tick()
        self.assertEqual(t1, 361.5)
        self.assertEqual(clock.tick_count, 1)
        self.assertEqual(clock.elapsed_minutes, 1.5)

        t2 = clock.tick()
        self.assertEqual(t2, 363.0)
        self.assertEqual(clock.tick_count, 2)
        self.assertEqual(clock.elapsed_minutes, 3.0)

    def test_clock_advance(self):
        clock = SimulationClock(start_time="06:00")
        clock.advance(15.0)
        self.assertEqual(clock.current_time, 375.0)
        self.assertEqual(clock.current_time_str, "06:15")
        self.assertEqual(clock.elapsed_minutes, 15.0)

        with self.assertRaises(ValueError):
            clock.advance(-5.0)

    def test_clock_advance_to(self):
        clock = SimulationClock(start_time="06:00")
        clock.advance_to("06:30")
        self.assertEqual(clock.current_time, 390.0)
        self.assertEqual(clock.current_time_str, "06:30")

        with self.assertRaises(ValueError):
            clock.advance_to("06:15")  # Earlier than current time

    def test_clock_reset(self):
        clock = SimulationClock(start_time="06:00")
        clock.advance(30.0)
        clock.reset()
        self.assertEqual(clock.current_time, 360.0)
        self.assertEqual(clock.tick_count, 0)
        self.assertEqual(clock.elapsed_minutes, 0.0)

        clock.reset(new_start_time="08:00")
        self.assertEqual(clock.start_time, 480.0)
        self.assertEqual(clock.current_time, 480.0)


class TestSimulationEvents(unittest.TestCase):
    """Unit tests for SimulationEvent and EventQueue."""

    def test_event_creation(self):
        ev = SimulationEvent(
            time="05:50",
            event_type=EventType.DEPARTURE,
            service_id="SRV_20607_01",
            node_id="MAS",
        )
        self.assertEqual(ev.time, 350.0)
        self.assertEqual(ev.event_type, EventType.DEPARTURE)
        self.assertEqual(ev.service_id, "SRV_20607_01")
        self.assertEqual(ev.node_id, "MAS")

    def test_event_queue_deterministic_ordering(self):
        queue = EventQueue()
        ev1 = queue.schedule(time="06:00", event_type=EventType.DEPARTURE, service_id="S1", priority=10)
        ev2 = queue.schedule(time="05:30", event_type=EventType.ARRIVAL, service_id="S2", priority=10)
        ev3 = queue.schedule(time="06:00", event_type=EventType.SECTION_ENTER, service_id="S3", priority=5) # higher priority
        ev4 = queue.schedule(time="06:00", event_type=EventType.ARRIVAL, service_id="S4", priority=10)     # later sequence

        self.assertEqual(len(queue), 4)
        self.assertFalse(queue.is_empty())

        # Expected pop order: ev2 (05:30), ev3 (06:00, prio 5), ev1 (06:00, prio 10, seq 1), ev4 (06:00, prio 10, seq 4)
        popped = [queue.pop() for _ in range(4)]
        self.assertEqual(popped[0].service_id, "S2")
        self.assertEqual(popped[1].service_id, "S3")
        self.assertEqual(popped[2].service_id, "S1")
        self.assertEqual(popped[3].service_id, "S4")
        self.assertTrue(queue.is_empty())
        self.assertIsNone(queue.pop())

    def test_peek_and_pop_until(self):
        queue = EventQueue()
        queue.schedule("05:00", EventType.SERVICE_START, "S1")
        queue.schedule("05:15", EventType.ARRIVAL, "S1")
        queue.schedule("05:30", EventType.DEPARTURE, "S1")
        queue.schedule("06:00", EventType.SERVICE_COMPLETE, "S1")

        self.assertEqual(queue.peek().time, 300.0)
        self.assertEqual(len(queue), 4)

        ready = queue.pop_until("05:20")
        self.assertEqual(len(ready), 2)
        self.assertEqual([e.time for e in ready], [300.0, 315.0])
        self.assertEqual(len(queue), 2)

    def test_cancel_events_for_service(self):
        queue = EventQueue()
        queue.schedule("05:00", EventType.DEPARTURE, "S1")
        queue.schedule("05:10", EventType.ARRIVAL, "S2")
        queue.schedule("05:20", EventType.ARRIVAL, "S1")
        queue.schedule("05:30", EventType.DEPARTURE, "S1")

        # Cancel only ARRIVAL events for S1
        canceled = queue.cancel_events_for_service("S1", EventType.ARRIVAL)
        self.assertEqual(canceled, 1)
        self.assertEqual(len(queue), 3)

        # Cancel all remaining events for S1
        canceled_all = queue.cancel_events_for_service("S1")
        self.assertEqual(canceled_all, 2)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue.peek().service_id, "S2")


class TestSimulationState(unittest.TestCase):
    """Unit tests for TrainRuntimeState and SimulationState with actual Network integration."""

    @classmethod
    def setUpClass(cls):
        cls.net = Network()
        cls.net.load_from_directory(_DATA_DIR)
        cls.net.load_trains(_TRAINS_FILE)
        cls.net.load_services(_SERVICES_FILE)
        cls.net.load_timetable(_TIMETABLE_FILE)

    def test_initialize_state_from_network(self):
        clock = SimulationClock(start_time="05:00")
        state = SimulationState(clock=clock)
        state.initialize_from_network(self.net)

        self.assertEqual(len(state.train_states), len(self.net.services))
        self.assertEqual(len(state.train_states), 47)

        # All services initially NOT_STARTED
        for svc_id, train_state in state.train_states.items():
            self.assertEqual(train_state.status, TrainStatus.NOT_STARTED)
            self.assertFalse(train_state.is_active)
            self.assertFalse(train_state.is_completed)
            self.assertEqual(train_state.delay_minutes, 0.0)

        # Verify specific train state for Vande Bharat 20607
        s20607 = state.get_train_state("SRV_20607_01")
        self.assertEqual(s20607.train_id, "TR_20607")
        self.assertEqual(s20607.route_id, "RT_WEST_MAS_AJJ")
        self.assertEqual(s20607.origin, "MAS")
        self.assertEqual(s20607.destination, "AJJ")
        self.assertEqual(s20607.priority_class, "HIGH")

    def test_resource_occupancy_and_locks(self):
        state = SimulationState()
        state.initialize_from_network(self.net)

        svc1 = "SRV_12607_01"
        svc2 = "SRV_12609_01"
        resource = "TRACK_SEC_01"

        # svc1 occupies resource
        self.assertTrue(state.occupy_resource(resource, svc1))
        self.assertTrue(state.is_resource_occupied(resource))
        self.assertEqual(state.get_resource_holder(resource), svc1)
        self.assertIn(resource, state.get_train_state(svc1).occupied_resources)

        # svc2 tries to occupy same resource -> rejected
        self.assertFalse(state.occupy_resource(resource, svc2))
        self.assertEqual(state.get_resource_holder(resource), svc1)

        # svc1 re-occupying same resource is idempotent True
        self.assertTrue(state.occupy_resource(resource, svc1))

        # svc2 tries to release resource it doesn't hold -> rejected
        self.assertFalse(state.release_resource(resource, svc2))

        # svc1 releases resource
        self.assertTrue(state.release_resource(resource, svc1))
        self.assertFalse(state.is_resource_occupied(resource))
        self.assertIsNone(state.get_resource_holder(resource))

    def test_service_lifecycle_and_state_transitions(self):
        state = SimulationState()
        state.initialize_from_network(self.net)
        svc_id = "SRV_20607_01"

        # 1. Start service at MAS
        state.start_service(svc_id, start_node="MAS", time="05:45")
        t_state = state.get_train_state(svc_id)
        self.assertEqual(t_state.status, TrainStatus.AT_STATION)
        self.assertEqual(t_state.current_station, "MAS")
        self.assertEqual(t_state.current_node, "MAS")
        self.assertIsNone(t_state.current_track_section)
        self.assertTrue(t_state.is_active)
        self.assertIn(svc_id, state.station_occupancy["MAS"])

        # 2. Depart MAS and enter track section
        state.depart_from_station(svc_id, station_id="MAS", time="05:50", scheduled_departure="05:50")
        self.assertEqual(t_state.actual_departures["MAS"], 350.0)
        self.assertEqual(t_state.delay_minutes, 0.0)

        state.enter_track_section(
            svc_id, track_section_id="TS_MAS_PER", from_node="MAS", to_node="PER", time="05:51"
        )
        self.assertEqual(t_state.status, TrainStatus.IN_TRANSIT)
        self.assertIsNone(t_state.current_station)
        self.assertEqual(t_state.current_node, "MAS")
        self.assertEqual(t_state.current_track_section, "TS_MAS_PER")
        self.assertNotIn(svc_id, state.station_occupancy["MAS"])
        self.assertIn(svc_id, state.track_occupancy["TS_MAS_PER"])
        self.assertTrue(state.is_resource_occupied("TS_MAS_PER"))

        # 3. Arrive at PER with 3 minutes delay
        state.arrive_at_station(
            svc_id, station_id="PER", time="06:03", scheduled_arrival="06:00", stop_sequence=2
        )
        self.assertEqual(t_state.status, TrainStatus.AT_STATION)
        self.assertEqual(t_state.current_station, "PER")
        self.assertIsNone(t_state.current_track_section)
        self.assertEqual(t_state.stop_sequence, 2)
        self.assertEqual(t_state.actual_arrivals["PER"], 363.0)
        self.assertEqual(t_state.delay_minutes, 3.0)
        self.assertEqual(t_state.max_delay_minutes, 3.0)
        self.assertNotIn(svc_id, state.track_occupancy["TS_MAS_PER"])
        self.assertFalse(state.is_resource_occupied("TS_MAS_PER"))

        # 4. Hold service at PER
        state.hold_service(svc_id, reason="Platform conflict")
        self.assertEqual(t_state.status, TrainStatus.HELD)
        self.assertTrue(t_state.is_active)

        # 5. Resume service
        state.resume_service(svc_id, new_status=TrainStatus.AT_STATION)
        self.assertEqual(t_state.status, TrainStatus.AT_STATION)

        # 6. Complete service at AJJ
        state.complete_service(svc_id, final_station="AJJ", time="07:00")
        self.assertEqual(t_state.status, TrainStatus.COMPLETED)
        self.assertTrue(t_state.is_completed)
        self.assertFalse(t_state.is_active)
        self.assertNotIn(svc_id, state.station_occupancy["PER"])

    def test_delay_analytics_and_queries(self):
        state = SimulationState()
        state.initialize_from_network(self.net)

        s1 = "SRV_12607_01"  # weight 1.0
        s2 = "SRV_20607_01"  # weight 1.0

        state.start_service(s1, "MAS", "06:00")
        state.start_service(s2, "MAS", "06:00")

        # Record delays
        state.get_train_state(s1).record_delay(5.0)
        state.get_train_state(s2).record_delay(12.0)

        self.assertEqual(state.get_total_delay_minutes(), 17.0)
        self.assertEqual(state.get_total_weighted_delay(), 17.0)

        delayed = state.get_delayed_services(threshold_minutes=10.0)
        self.assertEqual(len(delayed), 1)
        self.assertEqual(delayed[0].service_id, s2)

        active = state.get_active_services()
        self.assertEqual(len(active), 2)


class TestTrainSimulator(unittest.TestCase):
    """Unit tests for TrainSimulator: route order, directional lookups, movement, and missing tracks."""

    def setUp(self):
        """Construct an in-memory network with bidirectional corridor infrastructure."""
        self.net = Network()

        # Stations
        self.net.stations = {
            "MAS": {"id": "MAS", "name": "Chennai Central", "station_type": "Terminal", "platform_count": 15},
            "BBQ": {"id": "BBQ", "name": "Basin Bridge", "station_type": "Junction", "platform_count": 6},
            "VJM": {"id": "VJM", "name": "Vyasarpadi", "station_type": "Junction", "platform_count": 3},
            "PER": {"id": "PER", "name": "Perambur", "station_type": "Regular", "platform_count": 4},
        }
        # Platforms
        self.net.platforms = {
            "MAS_P1": {"id": "MAS_P1", "station_id": "MAS", "platform_number": 1, "platform_type": "Main", "capacity": 24}
        }
        # Track sections (DOWN and UP)
        from simulation.network import Station, Platform, TrackSection, Route, Train, Service, TimetableEntry
        self.net.stations = {k: Station(**v) for k, v in self.net.stations.items()}
        self.net.platforms = {k: Platform(**v) for k, v in self.net.platforms.items()}

        self.net.track_sections = {
            "TS_MAS_BBQ_DOWN": TrackSection(
                id="TS_MAS_BBQ_DOWN", from_node="MAS", to_node="BBQ", direction="DOWN",
                track_type="THROAT", number_of_tracks=2, travel_time_minutes=4.0,
                capacity=2, minimum_headway_minutes=3.0,
            ),
            "TS_BBQ_MAS_UP": TrackSection(
                id="TS_BBQ_MAS_UP", from_node="BBQ", to_node="MAS", direction="UP",
                track_type="THROAT", number_of_tracks=2, travel_time_minutes=4.0,
                capacity=2, minimum_headway_minutes=3.0,
            ),
            "TS_BBQ_VJM_DOWN": TrackSection(
                id="TS_BBQ_VJM_DOWN", from_node="BBQ", to_node="VJM", direction="DOWN",
                track_type="MAIN", number_of_tracks=2, travel_time_minutes=3.0,
                capacity=2, minimum_headway_minutes=3.0,
            ),
            "TS_VJM_BBQ_UP": TrackSection(
                id="TS_VJM_BBQ_UP", from_node="VJM", to_node="BBQ", direction="UP",
                track_type="MAIN", number_of_tracks=2, travel_time_minutes=3.0,
                capacity=2, minimum_headway_minutes=3.0,
            ),
            "TS_VJM_PER_DOWN": TrackSection(
                id="TS_VJM_PER_DOWN", from_node="VJM", to_node="PER", direction="DOWN",
                track_type="MAIN", number_of_tracks=2, travel_time_minutes=5.0,
                capacity=2, minimum_headway_minutes=3.0,
            ),
            "TS_PER_VJM_UP": TrackSection(
                id="TS_PER_VJM_UP", from_node="PER", to_node="VJM", direction="UP",
                track_type="MAIN", number_of_tracks=2, travel_time_minutes=5.0,
                capacity=2, minimum_headway_minutes=3.0,
            ),
        }

        # Routes (DOWN and UP)
        self.net.routes = {
            "RT_MAS_PER_DOWN": Route(
                id="RT_MAS_PER_DOWN", name="MAS to PER Down",
                origin="MAS", destination="PER", service_type="EXPRESS",
                ordered_nodes=["MAS", "BBQ", "VJM", "PER"],
            ),
            "RT_PER_MAS_UP": Route(
                id="RT_PER_MAS_UP", name="PER to MAS Up",
                origin="PER", destination="MAS", service_type="EXPRESS",
                ordered_nodes=["PER", "VJM", "BBQ", "MAS"],
            ),
        }

        # Trains
        self.net.trains = {
            "TR_101": Train(id="TR_101", name="Express Down", train_number="101", train_type="EXPRESS"),
            "TR_102": Train(id="TR_102", name="Express Up", train_number="102", train_type="EXPRESS"),
        }

        # Services
        self.net.services = {
            "SRV_DOWN_01": Service(
                id="SRV_DOWN_01", train_id="TR_101", origin="MAS", destination="PER",
                route_id="RT_MAS_PER_DOWN", operating_days=["MON"], priority_class="HIGH",
                delay_penalty_weight=1.0, simulation_profile="LOCO_ELECTRIC",
            ),
            "SRV_UP_01": Service(
                id="SRV_UP_01", train_id="TR_102", origin="PER", destination="MAS",
                route_id="RT_PER_MAS_UP", operating_days=["MON"], priority_class="HIGH",
                delay_penalty_weight=1.0, simulation_profile="LOCO_ELECTRIC",
            ),
        }

        # Timetables
        self.net.timetable = [
            TimetableEntry(service_id="SRV_DOWN_01", station_id="MAS", arrival=None, departure="06:00", stop_sequence=1),
            TimetableEntry(service_id="SRV_DOWN_01", station_id="PER", arrival="06:12", departure=None, stop_sequence=2),
            TimetableEntry(service_id="SRV_UP_01", station_id="PER", arrival=None, departure="07:00", stop_sequence=1),
            TimetableEntry(service_id="SRV_UP_01", station_id="MAS", arrival="07:12", departure=None, stop_sequence=2),
        ]

    def test_directional_track_lookup(self):
        from simulation.simulator import find_track_section

        # DOWN lookup
        ts_down = find_track_section(self.net, "MAS", "BBQ", direction="DOWN")
        self.assertIsNotNone(ts_down)
        self.assertEqual(ts_down.id, "TS_MAS_BBQ_DOWN")
        self.assertEqual(ts_down.direction, "DOWN")

        # UP lookup
        ts_up = find_track_section(self.net, "BBQ", "MAS", direction="UP")
        self.assertIsNotNone(ts_up)
        self.assertEqual(ts_up.id, "TS_BBQ_MAS_UP")
        self.assertEqual(ts_up.direction, "UP")

        # Non-existent link
        ts_none = find_track_section(self.net, "MAS", "PER")
        self.assertIsNone(ts_none)

    def test_normal_movement_down_direction_and_clock_advancement(self):
        from simulation.simulator import TrainSimulator

        clock = SimulationClock(start_time="06:00")
        sim = TrainSimulator(network=self.net, clock=clock)

        # 1. Initialize service
        start_ev = sim.initialize_service("SRV_DOWN_01")
        self.assertEqual(start_ev.event_type, EventType.SERVICE_START)
        self.assertEqual(start_ev.node_id, "MAS")
        self.assertEqual(clock.current_time, 360.0)

        # 2. Step 1: MAS -> BBQ (4.0 min)
        step1_events = sim.step_service("SRV_DOWN_01")
        # Events: DEPARTURE(MAS), SECTION_ENTER(TS_MAS_BBQ_DOWN), SECTION_EXIT(BBQ), ARRIVAL(BBQ)
        types1 = [e.event_type for e in step1_events]
        self.assertEqual(types1, [
            EventType.DEPARTURE,
            EventType.SECTION_ENTER,
            EventType.SECTION_EXIT,
            EventType.ARRIVAL,
        ])
        self.assertEqual(clock.current_time, 364.0)  # 06:00 + 4m = 06:04
        t_state = sim.state.get_train_state("SRV_DOWN_01")
        self.assertEqual(t_state.current_station, "BBQ")
        self.assertEqual(t_state.status, TrainStatus.AT_STATION)

        # 3. Step 2: BBQ -> VJM (3.0 min)
        step2_events = sim.step_service("SRV_DOWN_01")
        self.assertEqual(clock.current_time, 367.0)  # 06:04 + 3m = 06:07
        self.assertEqual(t_state.current_station, "VJM")

        # 4. Step 3: VJM -> PER (5.0 min, Destination)
        step3_events = sim.step_service("SRV_DOWN_01")
        types3 = [e.event_type for e in step3_events]
        self.assertEqual(types3, [
            EventType.DEPARTURE,
            EventType.SECTION_ENTER,
            EventType.SECTION_EXIT,
            EventType.ARRIVAL,
            EventType.SERVICE_COMPLETE,
        ])
        self.assertEqual(clock.current_time, 372.0)  # 06:07 + 5m = 06:12 (372 min)
        self.assertEqual(t_state.status, TrainStatus.COMPLETED)
        self.assertEqual(t_state.current_station, "PER")
        self.assertEqual(t_state.delay_minutes, 0.0)  # Scheduled arrival was 06:12, actual is 06:12

    def test_run_service_to_destination_up_direction(self):
        from simulation.simulator import TrainSimulator

        clock = SimulationClock(start_time="07:00")
        sim = TrainSimulator(network=self.net, clock=clock)

        events = sim.run_service_to_destination("SRV_UP_01")
        self.assertGreater(len(events), 0)

        # First event is SERVICE_START at PER, last is SERVICE_COMPLETE at MAS
        self.assertEqual(events[0].event_type, EventType.SERVICE_START)
        self.assertEqual(events[0].node_id, "PER")
        self.assertEqual(events[-1].event_type, EventType.SERVICE_COMPLETE)
        self.assertEqual(events[-1].node_id, "MAS")

        # Total travel time: PER->VJM (5m) + VJM->BBQ (3m) + BBQ->MAS (4m) = 12m
        self.assertEqual(clock.current_time, 432.0)  # 07:00 (420m) + 12m = 07:12 (432m)

        t_state = sim.state.get_train_state("SRV_UP_01")
        self.assertEqual(t_state.status, TrainStatus.COMPLETED)
        self.assertEqual(t_state.current_station, "MAS")

    def test_missing_track_section_raises_in_strict_mode(self):
        from simulation.simulator import TrainSimulator, MissingTrackSectionError

        # Remove TS_BBQ_VJM_DOWN from track sections
        del self.net.track_sections["TS_BBQ_VJM_DOWN"]

        clock = SimulationClock(start_time="06:00")
        sim = TrainSimulator(network=self.net, clock=clock)

        # Step 1: MAS -> BBQ works
        sim.step_service("SRV_DOWN_01")

        # Step 2: BBQ -> VJM missing -> raises MissingTrackSectionError
        with self.assertRaises(MissingTrackSectionError) as ctx:
            sim.step_service("SRV_DOWN_01", strict_track_lookup=True)

        self.assertEqual(ctx.exception.from_node, "BBQ")
        self.assertEqual(ctx.exception.to_node, "VJM")
        self.assertEqual(ctx.exception.service_id, "SRV_DOWN_01")

    def test_missing_track_section_fallback_in_non_strict_mode(self):
        from simulation.simulator import TrainSimulator

        # Remove TS_BBQ_VJM_DOWN
        del self.net.track_sections["TS_BBQ_VJM_DOWN"]

        clock = SimulationClock(start_time="06:00")
        sim = TrainSimulator(network=self.net, clock=clock)

        sim.step_service("SRV_DOWN_01", strict_track_lookup=False, fallback_travel_time_minutes=2.5)
        step2_events = sim.step_service("SRV_DOWN_01", strict_track_lookup=False, fallback_travel_time_minutes=2.5)

        # Travel time used fallback 2.5m
        self.assertIn("FALLBACK_BBQ_VJM", step2_events[0].track_section_id)
        self.assertEqual(clock.current_time, 366.5)  # 360 + 4.0 + 2.5

    def test_real_dataset_service_simulation(self):
        """Verify running a real dataset service (SRV_20607_01) on its loaded route."""
        from simulation.simulator import TrainSimulator

        real_net = Network()
        real_net.load_from_directory(_DATA_DIR)
        real_net.load_trains(_TRAINS_FILE)
        real_net.load_services(_SERVICES_FILE)
        real_net.load_timetable(_TIMETABLE_FILE)

        sim = TrainSimulator(network=real_net)
        events = sim.run_service_to_destination(
            "SRV_20607_01",
            strict_track_lookup=False,
            fallback_travel_time_minutes=3.0,
        )
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0].event_type, EventType.SERVICE_START)
        self.assertEqual(events[0].node_id, "MAS")
        self.assertEqual(events[-1].event_type, EventType.SERVICE_COMPLETE)
        self.assertEqual(events[-1].node_id, "AJJ")

        t_state = sim.state.get_train_state("SRV_20607_01")
        self.assertEqual(t_state.status, TrainStatus.COMPLETED)
        self.assertEqual(t_state.current_station, "AJJ")


class TestTrackSectionOccupancy(unittest.TestCase):
    """Unit tests for Batch 5: Track section occupancy, exit, release, and capacity enforcement."""

    def setUp(self):
        from simulation.network import Network, Station, TrackSection, Route, Train, Service

        self.net = Network()
        self.net.stations = {
            "MAS": Station(id="MAS", name="Chennai Central", station_type="Terminal", platform_count=15),
            "BBQ": Station(id="BBQ", name="Basin Bridge", station_type="Junction", platform_count=6),
            "VJM": Station(id="VJM", name="Vyasarpadi", station_type="Junction", platform_count=3),
        }
        self.net.track_sections = {
            "TS_SINGLE_CAP": TrackSection(
                id="TS_SINGLE_CAP", from_node="MAS", to_node="BBQ", direction="DOWN",
                track_type="MAIN", number_of_tracks=1, travel_time_minutes=4.0,
                capacity=1, minimum_headway_minutes=3.0,
            ),
            "TS_MULTI_CAP": TrackSection(
                id="TS_MULTI_CAP", from_node="BBQ", to_node="VJM", direction="DOWN",
                track_type="THROAT", number_of_tracks=2, travel_time_minutes=3.0,
                capacity=2, minimum_headway_minutes=2.0,
            ),
        }
        self.net.routes = {
            "RT_MAS_VJM": Route(
                id="RT_MAS_VJM", name="MAS to VJM", origin="MAS", destination="VJM",
                service_type="EXPRESS", ordered_nodes=["MAS", "BBQ", "VJM"],
            )
        }
        self.net.trains = {
            "TR_1": Train(id="TR_1", name="Train 1", train_number="1001", train_type="EXPRESS"),
            "TR_2": Train(id="TR_2", name="Train 2", train_number="1002", train_type="EXPRESS"),
            "TR_3": Train(id="TR_3", name="Train 3", train_number="1003", train_type="EXPRESS"),
        }
        self.net.services = {
            "SRV_1": Service(
                id="SRV_1", train_id="TR_1", origin="MAS", destination="VJM",
                route_id="RT_MAS_VJM", operating_days=["MON"], priority_class="HIGH",
                delay_penalty_weight=1.0, simulation_profile="LOCO",
            ),
            "SRV_2": Service(
                id="SRV_2", train_id="TR_2", origin="MAS", destination="VJM",
                route_id="RT_MAS_VJM", operating_days=["MON"], priority_class="HIGH",
                delay_penalty_weight=1.0, simulation_profile="LOCO",
            ),
            "SRV_3": Service(
                id="SRV_3", train_id="TR_3", origin="MAS", destination="VJM",
                route_id="RT_MAS_VJM", operating_days=["MON"], priority_class="HIGH",
                delay_penalty_weight=1.0, simulation_profile="LOCO",
            ),
        }

    def test_1_enter_section_creates_occupancy_record(self):
        """Entering a section creates a valid TrackSectionOccupancy record with entry and expected exit times."""
        state = SimulationState()
        state.initialize_from_network(self.net)

        rec = state.enter_track_section(
            service_id="SRV_1",
            track_section_id="TS_SINGLE_CAP",
            from_node="MAS",
            to_node="BBQ",
            time="06:00",
            expected_exit_time="06:04",
            capacity=1,
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec.section_id, "TS_SINGLE_CAP")
        self.assertEqual(rec.service_id, "SRV_1")
        self.assertEqual(rec.train_id, "TR_1")
        self.assertEqual(rec.entry_time, 360.0)
        self.assertEqual(rec.expected_exit_time, 364.0)
        self.assertIsNone(rec.actual_exit_time)
        self.assertTrue(rec.is_active)

        self.assertEqual(state.get_section_occupancy_count("TS_SINGLE_CAP"), 1)
        self.assertIn("TS_SINGLE_CAP", state.get_train_state("SRV_1").occupied_resources)

    def test_2_exit_section_records_actual_exit_time(self):
        """Exiting a section records actual_exit_time and marks occupancy record inactive."""
        state = SimulationState()
        state.initialize_from_network(self.net)

        state.enter_track_section(
            service_id="SRV_1",
            track_section_id="TS_SINGLE_CAP",
            from_node="MAS",
            to_node="BBQ",
            time="06:00",
            expected_exit_time="06:04",
            capacity=1,
        )
        rec = state.exit_track_section("SRV_1", "TS_SINGLE_CAP", time="06:05")

        self.assertIsNotNone(rec)
        self.assertEqual(rec.actual_exit_time, 365.0)
        self.assertFalse(rec.is_active)
        self.assertEqual(rec.duration_minutes, 5.0)

    def test_3_occupancy_release_decreases_active_count(self):
        """Releasing occupancy decrements count to 0 and frees section resource."""
        state = SimulationState()
        state.initialize_from_network(self.net)

        state.enter_track_section(
            service_id="SRV_1",
            track_section_id="TS_SINGLE_CAP",
            from_node="MAS",
            to_node="BBQ",
            time="06:00",
            capacity=1,
        )
        self.assertEqual(state.get_section_occupancy_count("TS_SINGLE_CAP"), 1)
        self.assertFalse(state.is_section_available("TS_SINGLE_CAP", capacity=1))

        # Arrive at station releases track section
        state.arrive_at_station(
            service_id="SRV_1",
            station_id="BBQ",
            time="06:04",
        )
        self.assertEqual(state.get_section_occupancy_count("TS_SINGLE_CAP"), 0)
        self.assertTrue(state.is_section_available("TS_SINGLE_CAP", capacity=1))
        self.assertNotIn("TS_SINGLE_CAP", state.get_train_state("SRV_1").occupied_resources)

    def test_4_capacity_violation_detected_and_raised(self):
        """Attempting to enter a full section raises CapacityViolationError with complete details."""
        from simulation.state import CapacityViolationError

        state = SimulationState()
        state.initialize_from_network(self.net)

        # First train occupies capacity=1 section
        state.enter_track_section(
            service_id="SRV_1",
            track_section_id="TS_SINGLE_CAP",
            from_node="MAS",
            to_node="BBQ",
            time="06:00",
            capacity=1,
        )

        # Second train attempts to enter same section -> capacity violation
        with self.assertRaises(CapacityViolationError) as ctx:
            state.enter_track_section(
                service_id="SRV_2",
                track_section_id="TS_SINGLE_CAP",
                from_node="MAS",
                to_node="BBQ",
                time="06:01",
                capacity=1,
            )

        err = ctx.exception
        self.assertEqual(err.section_id, "TS_SINGLE_CAP")
        self.assertEqual(err.service_id, "SRV_2")
        self.assertEqual(err.train_id, "TR_2")
        self.assertEqual(err.current_occupancy, 1)
        self.assertEqual(err.capacity, 1)
        self.assertIn("SRV_1", err.active_services)

    def test_5_two_trains_competing_for_one_section(self):
        """Two trains competing: on capacity=1 section, train 2 waits until train 1 exits.

        On capacity=2 section, both trains can occupy simultaneously; a third is rejected.
        """
        from simulation.state import CapacityViolationError

        state = SimulationState()
        state.initialize_from_network(self.net)

        # Case A: Single-capacity section competition
        state.enter_track_section("SRV_1", "TS_SINGLE_CAP", "MAS", "BBQ", time="06:00", capacity=1)
        self.assertFalse(state.is_section_available("TS_SINGLE_CAP", capacity=1))

        # SRV_2 blocked
        with self.assertRaises(CapacityViolationError):
            state.enter_track_section("SRV_2", "TS_SINGLE_CAP", "MAS", "BBQ", time="06:01", capacity=1)

        # SRV_1 clears section at BBQ
        state.arrive_at_station("SRV_1", "BBQ", time="06:04")
        self.assertTrue(state.is_section_available("TS_SINGLE_CAP", capacity=1))

        # Now SRV_2 successfully enters
        rec2 = state.enter_track_section("SRV_2", "TS_SINGLE_CAP", "MAS", "BBQ", time="06:04", capacity=1)
        self.assertEqual(rec2.service_id, "SRV_2")
        self.assertEqual(state.get_section_occupancy_count("TS_SINGLE_CAP"), 1)

        # Case B: Multi-capacity (capacity=2) section
        state.enter_track_section("SRV_1", "TS_MULTI_CAP", "BBQ", "VJM", time="06:05", capacity=2)
        state.enter_track_section("SRV_2", "TS_MULTI_CAP", "BBQ", "VJM", time="06:06", capacity=2)
        self.assertEqual(state.get_section_occupancy_count("TS_MULTI_CAP"), 2)
        self.assertFalse(state.is_section_available("TS_MULTI_CAP", capacity=2))

        # SRV_3 blocked on capacity=2 section
        with self.assertRaises(CapacityViolationError):
            state.enter_track_section("SRV_3", "TS_MULTI_CAP", "BBQ", "VJM", time="06:07", capacity=2)


if __name__ == "__main__":
    unittest.main()



