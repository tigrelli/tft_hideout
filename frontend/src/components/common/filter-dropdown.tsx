export interface FilterOption {
  value: string;
  label: string;
}

// FE-11: 필터 UI 반응형 공용 컴포넌트 중 순수 셀렉트 부분. 값 타입을 항상
// string으로 통일해 화면별 값 타입(문자열 유니온, 숫자 id 등)은 호출부에서
// 얇게 변환하고, 렌더링·스타일은 이 컴포넌트 하나로 통일한다.
export function FilterDropdown({
  label,
  value,
  options,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  options: readonly FilterOption[];
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="flex items-center gap-2 text-body text-text-primary">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-control border border-border-input px-2 py-1.5"
      >
        {placeholder !== undefined && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
