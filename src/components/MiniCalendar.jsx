import React, { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function daysInMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
}

function toDateKey(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function isoToDateKey(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return toDateKey(d);
}

/**
 * MiniCalendar – compact month grid.
 *
 * Props:
 *   scheduledDates  – array of ISO date strings that have scheduled posts
 *   selectedDate    – currently selected date key (YYYY-MM-DD) or ''
 *   onSelectDate    – callback(dateKey) when a day is clicked
 *   compact         – if true, renders a smaller version for inline use
 */
export default function MiniCalendar({
  scheduledDates = [],
  selectedDate = '',
  onSelectDate,
  compact = false,
}) {
  const [viewDate, setViewDate] = useState(() => {
    if (selectedDate) {
      const d = new Date(selectedDate);
      if (!Number.isNaN(d.getTime())) return startOfMonth(d);
    }
    return startOfMonth(new Date());
  });

  const monthLabel = viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  const prevMonth = () => {
    setViewDate((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1));
  };
  const nextMonth = () => {
    setViewDate((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1));
  };

  // Build set of date-keys that have posts
  const busySet = useMemo(() => {
    const set = new Set();
    scheduledDates.forEach((iso) => {
      const key = isoToDateKey(iso);
      if (key) set.add(key);
    });
    return set;
  }, [scheduledDates]);

  // Build grid cells
  const cells = useMemo(() => {
    const firstDay = startOfMonth(viewDate);
    // Monday = 0 … Sunday = 6
    let startDow = firstDay.getDay() - 1;
    if (startDow < 0) startDow = 6;

    const total = daysInMonth(viewDate);
    const rows = [];
    let current = [];

    // Leading blanks
    for (let i = 0; i < startDow; i++) current.push(null);

    for (let day = 1; day <= total; day++) {
      const dateKey = toDateKey(new Date(viewDate.getFullYear(), viewDate.getMonth(), day));
      current.push({ day, dateKey });
      if (current.length === 7) {
        rows.push(current);
        current = [];
      }
    }
    // Trailing blanks
    if (current.length > 0) {
      while (current.length < 7) current.push(null);
      rows.push(current);
    }
    return rows;
  }, [viewDate]);

  const todayKey = toDateKey(new Date());

  const cellSize = compact ? 'w-7 h-7 text-xs' : 'w-9 h-9 text-sm';

  return (
    <div className={compact ? '' : ''}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <button
          type="button"
          onClick={prevMonth}
          className="p-1 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <ChevronLeft size={compact ? 14 : 16} className="text-gray-500" />
        </button>
        <span className={`font-semibold text-gray-800 ${compact ? 'text-xs' : 'text-sm'}`}>
          {monthLabel}
        </span>
        <button
          type="button"
          onClick={nextMonth}
          className="p-1 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <ChevronRight size={compact ? 14 : 16} className="text-gray-500" />
        </button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 mb-1">
        {DAY_LABELS.map((d) => (
          <div key={d} className={`text-center font-medium text-gray-400 ${compact ? 'text-[10px]' : 'text-xs'}`}>
            {compact ? d.charAt(0) : d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7">
        {cells.flat().map((cell, i) => {
          if (!cell) {
            return <div key={`blank-${i}`} className={cellSize} />;
          }
          const isToday = cell.dateKey === todayKey;
          const isSelected = cell.dateKey === selectedDate;
          const hasPosts = busySet.has(cell.dateKey);

          return (
            <button
              key={cell.dateKey}
              type="button"
              onClick={() => onSelectDate?.(cell.dateKey)}
              className={`
                ${cellSize} flex flex-col items-center justify-center rounded-lg transition-all relative
                ${isSelected
                  ? 'bg-purple-600 text-white font-bold'
                  : isToday
                    ? 'bg-purple-50 text-purple-700 font-semibold'
                    : 'text-gray-700 hover:bg-gray-100'
                }
              `}
            >
              <span>{cell.day}</span>
              {hasPosts && (
                <span
                  className={`absolute bottom-0.5 w-1.5 h-1.5 rounded-full ${
                    isSelected ? 'bg-white' : 'bg-purple-500'
                  }`}
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export { isoToDateKey, toDateKey };
