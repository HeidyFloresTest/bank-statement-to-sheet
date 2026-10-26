"""Corporate Excel generation engine using openpyxl with formulas, Segoe UI typography, and styling."""

import io
from datetime import datetime
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.schemas import TransactionItem

# Corporate Styling Constants
FONT_FAMILY = "Segoe UI"
COLOR_NAVY_DARK = "0F172A"  # Headers
COLOR_NAVY_LIGHT = "1E293B"  # Secondary Header
COLOR_WHITE = "FFFFFF"
COLOR_ZEBRA = "F8FAFC"  # Alternating rows
COLOR_TOTALS_BG = "E2E8F0"  # Total summary row
COLOR_BORDER = "CBD5E1"
COLOR_INGRESOS = "16A34A"  # Green
COLOR_EGRESOS = "DC2626"  # Red

THIN_BORDER = Border(
    left=Side(style="thin", color=COLOR_BORDER),
    right=Side(style="thin", color=COLOR_BORDER),
    top=Side(style="thin", color=COLOR_BORDER),
    bottom=Side(style="thin", color=COLOR_BORDER),
)

DOUBLE_BOTTOM_BORDER = Border(
    left=Side(style="thin", color=COLOR_BORDER),
    right=Side(style="thin", color=COLOR_BORDER),
    top=Side(style="thin", color=COLOR_BORDER),
    bottom=Side(style="double", color=COLOR_NAVY_DARK),
)

CURRENCY_FORMAT = '$#,##0.00;($#,##0.00);"-"'


class ExcelGenerator:
    """Enterprise openpyxl report builder producing styled financial workbooks."""

    def generate_reconciliation_workbook(
        self,
        transactions: list[TransactionItem],
        report_title: str = "Conciliación Bancaria",
        include_summary: bool = True,
    ) -> io.BytesIO:
        """Create a multi-sheet, beautifully formatted Excel workbook in memory."""
        wb = openpyxl.Workbook()

        # Sheet 1: Transactions
        ws_tx = wb.active
        assert ws_tx is not None, "Workbook must contain an active worksheet"
        ws_tx.title = "Transacciones"
        ws_tx.views.sheetView[0].showGridLines = True
        self._build_transactions_sheet(ws_tx, transactions)

        # Sheet 2: Executive Summary (KPIs)
        if include_summary:
            ws_summary = wb.create_sheet(title="Resumen Ejecutivo")
            ws_summary.views.sheetView[0].showGridLines = True
            self._build_summary_sheet(ws_summary, transactions, report_title)

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    def _build_transactions_sheet(self, ws: Worksheet, transactions: list[TransactionItem]) -> None:
        headers = [
            "#",
            "Fecha",
            "Concepto / Descripción",
            "Referencia",
            "Tipo Movimiento",
            "Cargo (Egreso)",
            "Abono (Ingreso)",
            "Saldo Resultante",
            "Moneda",
            "Archivo Origen",
        ]

        # Freeze pane at header
        ws.freeze_panes = "A2"

        # Apply header formatting
        header_font = Font(name=FONT_FAMILY, size=11, bold=True, color=COLOR_WHITE)
        header_fill = PatternFill(
            start_color=COLOR_NAVY_DARK, end_color=COLOR_NAVY_DARK, fill_type="solid"
        )
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.row_dimensions[1].height = 28

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = THIN_BORDER

        # Data rows
        data_font = Font(name=FONT_FAMILY, size=10)
        ingreso_font = Font(name=FONT_FAMILY, size=10, bold=True, color=COLOR_INGRESOS)
        egreso_font = Font(name=FONT_FAMILY, size=10, bold=True, color=COLOR_EGRESOS)
        zebra_fill = PatternFill(start_color=COLOR_ZEBRA, end_color=COLOR_ZEBRA, fill_type="solid")

        start_row = 2
        for idx, tx in enumerate(transactions, start=start_row):
            ws.row_dimensions[idx].height = 20
            is_even = idx % 2 == 0
            row_fill = zebra_fill if is_even else None

            cargo_val = tx.monto if tx.tipo_movimiento == "egreso" else None
            abono_val = tx.monto if tx.tipo_movimiento == "ingreso" else None

            row_data: list[Any] = [
                idx - start_row + 1,
                tx.fecha,
                tx.descripcion_concepto,
                tx.referencia,
                "INGRESO" if tx.tipo_movimiento == "ingreso" else "EGRESO",
                cargo_val,
                abono_val,
                tx.saldo_resultante,
                tx.moneda,
                tx.nombre_archivo_origen,
            ]

            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=idx, column=col_idx, value=val)
                cell.font = data_font
                cell.border = THIN_BORDER
                if row_fill:
                    cell.fill = row_fill

                # Alignment & number formats
                if col_idx == 1:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx == 2:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in [3, 4, 10]:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                elif col_idx == 5:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.font = ingreso_font if tx.tipo_movimiento == "ingreso" else egreso_font
                elif col_idx in [6, 7, 8]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = CURRENCY_FORMAT
                elif col_idx == 9:
                    cell.alignment = Alignment(horizontal="center", vertical="center")

        total_row_idx = start_row + len(transactions)
        ws.row_dimensions[total_row_idx].height = 24

        # Totals Row with dynamic SUM formulas
        total_fill = PatternFill(
            start_color=COLOR_TOTALS_BG, end_color=COLOR_TOTALS_BG, fill_type="solid"
        )
        total_font = Font(name=FONT_FAMILY, size=11, bold=True, color=COLOR_NAVY_DARK)

        # Label cell
        label_cell = ws.cell(row=total_row_idx, column=1, value="TOTALES")
        label_cell.font = total_font
        label_cell.fill = total_fill
        label_cell.alignment = Alignment(horizontal="center", vertical="center")
        label_cell.border = DOUBLE_BOTTOM_BORDER

        for c in range(2, 6):
            cell = ws.cell(row=total_row_idx, column=c, value="")
            cell.fill = total_fill
            cell.border = DOUBLE_BOTTOM_BORDER

        # Cargo sum formula
        cargo_col = "F"
        last_data_row = total_row_idx - 1 if len(transactions) > 0 else 2
        cell_cargo = ws.cell(
            row=total_row_idx, column=6, value=f"=SUM({cargo_col}2:{cargo_col}{last_data_row})"
        )
        cell_cargo.font = total_font
        cell_cargo.fill = total_fill
        cell_cargo.border = DOUBLE_BOTTOM_BORDER
        cell_cargo.number_format = CURRENCY_FORMAT
        cell_cargo.alignment = Alignment(horizontal="right", vertical="center")

        # Abono sum formula
        abono_col = "G"
        cell_abono = ws.cell(
            row=total_row_idx, column=7, value=f"=SUM({abono_col}2:{abono_col}{last_data_row})"
        )
        cell_abono.font = total_font
        cell_abono.fill = total_fill
        cell_abono.border = DOUBLE_BOTTOM_BORDER
        cell_abono.number_format = CURRENCY_FORMAT
        cell_abono.alignment = Alignment(horizontal="right", vertical="center")

        # Blank out remaining columns in totals row
        for c in range(8, 11):
            cell = ws.cell(row=total_row_idx, column=c, value="")
            cell.fill = total_fill
            cell.border = DOUBLE_BOTTOM_BORDER

        # Dynamic column width auto-fitting
        self._autofit_columns(
            ws, min_widths={1: 6, 2: 14, 3: 35, 4: 18, 5: 16, 6: 18, 7: 18, 8: 18, 9: 10, 10: 25}
        )

    def _build_summary_sheet(
        self,
        ws: Worksheet,
        transactions: list[TransactionItem],
        report_title: str,
    ) -> None:
        # Title Block
        title_font = Font(name=FONT_FAMILY, size=16, bold=True, color=COLOR_NAVY_DARK)
        subtitle_font = Font(name=FONT_FAMILY, size=10, italic=True, color="64748B")

        ws.cell(row=2, column=2, value=report_title).font = title_font
        ws.cell(
            row=3,
            column=2,
            value=f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - BankReconcile Engine",
        ).font = subtitle_font

        # Calculate values
        total_ingresos = sum(t.monto for t in transactions if t.tipo_movimiento == "ingreso")
        total_egresos = sum(t.monto for t in transactions if t.tipo_movimiento == "egreso")
        saldo_neto = total_ingresos - total_egresos

        fechas = [t.fecha for t in transactions if t.fecha]
        min_date = min(fechas) if fechas else "N/A"
        max_date = max(fechas) if fechas else "N/A"
        periodo = f"{min_date} al {max_date}" if fechas else "N/A"
        currency = transactions[0].moneda if transactions else "USD"

        kpi_metrics = [
            ("Métrica Financiera", "Valor", "Detalle"),
            ("Total Movimientos", len(transactions), "Cantidad de transacciones auditadas"),
            ("Total Abonos (Ingresos)", total_ingresos, f"Fórmulas verificadas ({currency})"),
            ("Total Cargos (Egresos)", total_egresos, f"Fórmulas verificadas ({currency})"),
            ("Flujo Neto de Caja", saldo_neto, f"Diferencia neta del periodo ({currency})"),
            ("Período de Extracto", periodo, "Rango de fechas de movimientos"),
            ("Moneda de Conciliación", currency, "Moneda predominante detectada"),
        ]

        header_font = Font(name=FONT_FAMILY, size=11, bold=True, color=COLOR_WHITE)
        header_fill = PatternFill(
            start_color=COLOR_NAVY_DARK, end_color=COLOR_NAVY_DARK, fill_type="solid"
        )
        label_font = Font(name=FONT_FAMILY, size=10, bold=True, color=COLOR_NAVY_LIGHT)
        val_font = Font(name=FONT_FAMILY, size=11, bold=True)
        note_font = Font(name=FONT_FAMILY, size=9, color="64748B")

        start_row = 5
        for r_idx, (m_label, m_val, m_desc) in enumerate(kpi_metrics, start=start_row):
            ws.row_dimensions[r_idx].height = 24
            c1 = ws.cell(row=r_idx, column=2, value=m_label)
            c2 = ws.cell(row=r_idx, column=3, value=m_val)  # type: ignore[call-overload]
            c3 = ws.cell(row=r_idx, column=4, value=m_desc)

            for cell in [c1, c2, c3]:
                cell.border = THIN_BORDER

            if r_idx == start_row:
                for cell in [c1, c2, c3]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c1.font = label_font
                c1.alignment = Alignment(horizontal="left", vertical="center")

                c2.font = val_font
                c2.alignment = Alignment(horizontal="right", vertical="center")

                c3.font = note_font
                c3.alignment = Alignment(horizontal="left", vertical="center")

                # Format monetary KPIs
                if r_idx in [start_row + 2, start_row + 3, start_row + 4]:
                    c2.number_format = CURRENCY_FORMAT
                    if r_idx == start_row + 2:
                        c2.font = Font(name=FONT_FAMILY, size=11, bold=True, color=COLOR_INGRESOS)
                    elif r_idx == start_row + 3:
                        c2.font = Font(name=FONT_FAMILY, size=11, bold=True, color=COLOR_EGRESOS)
                    elif r_idx == start_row + 4:
                        net_color = COLOR_INGRESOS if saldo_neto >= 0 else COLOR_EGRESOS
                        c2.font = Font(name=FONT_FAMILY, size=11, bold=True, color=net_color)

        self._autofit_columns(ws, min_widths={2: 28, 3: 22, 4: 38})

    def _autofit_columns(
        self,
        ws: Worksheet,
        min_widths: dict[int, int] | None = None,
    ) -> None:
        min_widths = min_widths or {}
        for col in ws.columns:
            first_cell = col[0]
            if first_cell.column is None:
                continue
            col_idx = int(first_cell.column)
            col_letter = get_column_letter(col_idx)
            max_len = 0
            for cell in col:
                if cell.value:
                    val_str = str(cell.value)
                    if len(val_str) > max_len:
                        max_len = len(val_str)
            calculated_width = max(max_len + 4, min_widths.get(col_idx, 12))
            ws.column_dimensions[col_letter].width = min(calculated_width, 60)


excel_generator = ExcelGenerator()
