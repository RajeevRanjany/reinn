import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  numeric?: boolean;
}

export function DataTable<T>({
  rows,
  columns,
  caption,
  maxHeight = 360,
}: {
  rows: T[];
  columns: Column<T>[];
  caption?: string;
  maxHeight?: number;
}) {
  return (
    <div className="table-wrap" style={{ maxHeight }}>
      <table>
        {caption && <caption>{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.numeric ? "num" : ""} scope="col">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? "num" : ""}>
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
