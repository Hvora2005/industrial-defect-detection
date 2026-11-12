import { filterHistory } from "./format";
const rows = [
  {
    id: 1,
    timestamp: "2026-11-11T18:00:00Z",
    status: "FAIL",
    defects_found: 2,
    primary_defect: "scratches",
    primary_confidence: 80,
    severity: "MAJOR",
  },
  {
    id: 2,
    timestamp: "2026-11-12T18:00:00Z",
    status: "NO_DETECTIONS",
    defects_found: 0,
    primary_defect: null,
    primary_confidence: null,
    severity: null,
  },
];
test("search supports translated labels, status and date on loaded records", () => {
  expect(
    filterHistory(rows, "rayaduras", "FAIL", "2026-11-11", "2026-11-11").map(
      (r) => r.id,
    ),
  ).toEqual([1]);
  expect(
    filterHistory(rows, "", "NO_DETECTIONS", "", "").map((r) => r.id),
  ).toEqual([2]);
  expect(filterHistory(rows, "desconocido", "", "", "")).toEqual([]);
  expect(filterHistory(rows, "", "", "2026-11-12", "2026-11-11")).toEqual([]);
});
