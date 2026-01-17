/**
 * Pie chart utilities for SVG rendering.
 */

export interface PieSliceInput {
  label: string;
  value: number;
  color: string;
}

export interface PieSlice {
  label: string;
  value: number;
  color: string;
  percentage: number;
  path: string;
}

const TAU = Math.PI * 2;

function polarToCartesian(
  cx: number,
  cy: number,
  radius: number,
  angleInRadians: number
) {
  return {
    x: cx + radius * Math.cos(angleInRadians),
    y: cy + radius * Math.sin(angleInRadians),
  };
}

function describeArc(
  cx: number,
  cy: number,
  radius: number,
  startAngle: number,
  endAngle: number
) {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= Math.PI ? '0' : '1';

  return [
    `M ${cx} ${cy}`,
    `L ${start.x} ${start.y}`,
    `A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`,
    'Z',
  ].join(' ');
}

/**
 * Build pie slices for an SVG chart.
 */
export function buildPieSlices(
  slices: PieSliceInput[],
  options: { radius?: number; center?: number } = {}
): PieSlice[] {
  if (!slices.length) return [];
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);
  if (!total) return [];

  const radius = options.radius ?? 70;
  const center = options.center ?? 80;

  let currentAngle = -Math.PI / 2;
  let consumed = 0;

  return slices.map((slice, index) => {
    const isLast = index === slices.length - 1;
    const portion = slice.value / total;
    const angle = isLast ? TAU - consumed : portion * TAU;
    const startAngle = currentAngle;
    const endAngle = currentAngle + angle;
    currentAngle = endAngle;
    consumed += angle;

    return {
      label: slice.label,
      value: slice.value,
      color: slice.color,
      percentage: (angle / TAU) * 100,
      path: describeArc(center, center, radius, startAngle, endAngle),
    };
  });
}
