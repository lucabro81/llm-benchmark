/**
 * EXAMPLE: Status badge column using Record<Status, string> lookup maps.
 *
 * Patterns shown:
 * - Define a Status type as union of string literals
 * - Use Record<Status, string> for label and CSS class maps
 * - row.getValue("status") as Status — cast to typed status
 * - h("span", { class: dynamicClass }, labelText) renders the badge
 */

import type { Column } from "elements";
import { h } from "vue";

type ItemStatus = "active" | "inactive" | "pending" | "suspended";

interface Item {
  id: string;
  name: string;
  status: ItemStatus;
}

// Map each status to a human-readable label
const statusLabels: Record<ItemStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  pending: "Pending",
  suspended: "Suspended",
};

// Map each status to Tailwind CSS classes for the badge
const statusClasses: Record<ItemStatus, string> = {
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-800",
  pending: "bg-yellow-100 text-yellow-800",
  suspended: "bg-red-100 text-red-800",
};

export const columns: Column<Item>[] = [
  {
    id: "name",
    label: "Name",
    isSortable: true,
  },
  {
    id: "status",
    label: "Status",
    cell: ({ row }) => {
      // Cast the raw value to the typed status
      const status = row.getValue("status") as ItemStatus;
      return h(
        "span",
        {
          class: `inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${statusClasses[status]}`,
        },
        statusLabels[status],
      );
    },
  },
];
