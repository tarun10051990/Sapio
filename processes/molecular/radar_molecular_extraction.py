# NOTE: Partial transcription of neogenomics-webhooks/processes/molecular/radar_molecular_extraction.py
# taken from screenshots (lines ~433-593 of the original file). Imports, constants, data type models and the
# other handlers in this module (lines 1-432 and 594+) were not visible and are not reproduced here.

from datetime import timedelta


class AddRecordToPKDigestionScanRackPrepEntry(NeoWebhookHandler):

    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        scan_rack_prep_details: list[ELNSampleDetailModel] = self.exp_handler.get_step_models(PK_DIGESTION_SCAN_RACK_PREPARATION_ENTRY, ELNSampleDetailModel)
        parent_samples: list[ELNSampleDetailModel] = self.exp_handler.get_step_models(PARENT_SPECIMENS_ENTRY, ELNSampleDetailModel)
        if len(parent_samples) > 0:
            self.add_patient_samples(parent_samples, scan_rack_prep_details, PK_DIGESTION_SCAN_RACK_PREPARATION_ENTRY)
            self.add_patient_samples(parent_samples, scan_rack_prep_details, EXTRACTION_DNA_ISOLATES_ENTRY)
            sample_models = self.get_specimen_models(parent_samples)
            if len(sample_models) > 0:
                self.create_derivative_sample_record_placeholder(sample_models)

        controls: list[ELNExperimentDetailModel] = self.exp_handler.get_step_models(CONTROLS_ENTRY, ELNExperimentDetailModel)
        controls_helper = RadarControlsHelper(self, context)
        error = controls_helper.finalize_controls(controls, len(parent_samples))
        if error is not None:
            self.exp_handler.unlock_step(CONTROLS_ENTRY)
            return SapioWebhookResult(False, display_text=error)
        if len(controls) > 0:
            sample_models = self.add_control_samples(controls, scan_rack_prep_details, len(parent_samples), PK_DIGESTION_SCAN_RACK_PREPARATION_ENTRY)
            self.add_control_samples(controls, scan_rack_prep_details, len(parent_samples), EXTRACTION_DNA_ISOLATES_ENTRY)
            if len(sample_models) > 0:
                self.create_derivative_sample_record_placeholder(sample_models)

        self.rec_man.store_and_commit()
        experiment_model = self.exp_handler.get_experiment_model(ELNExperimentModel)
        self.rel_man.load_children_of_type([experiment_model], SampleModel)
        child_sample_models: list[SampleModel] = experiment_model.get_children_of_type(SampleModel)
        extracted_dna_samples: list[SampleModel] = [child_sample for child_sample in child_sample_models if child_sample.get_C_MaterialType_field() == "Extracted DNA"]
        if len(extracted_dna_samples) > 0:
            self.exp_handler.add_step_records(EXTRACTED_DNA_SAMPLES_ENTRY, extracted_dna_samples)
        self.rec_man.store_and_commit()
        return SapioWebhookResult(True)

    def get_extracted_dna_records(self, parent_sample_models: list[SampleModel]):
        self.rel_man.load_children_of_type(parent_sample_models, SampleModel)
        child_sample_models: list[SampleModel] = []
        for each_parent in parent_sample_models:
            child_records: list[SampleModel] = each_parent.get_children_of_type(SampleModel)
            if len(child_records) > 0:
                for child_record in child_records:
                    if child_record.get_C_MaterialType_field() == "Extracted DNA":
                        child_sample_models.append(child_record)
        return child_sample_models

    def create_derivative_sample_record_placeholder(self, parent_sample_models: list[SampleModel]):
        experiment_model: ELNExperimentModel = self.exp_handler.get_experiment_model(ELNExperimentModel)
        for parent_sample in parent_sample_models:
            child_sample_model = self.inst_man.add_new_record_of_type(SampleModel)
            child_sample_model.set_C_MaterialType_field("Extracted DNA")
            child_sample_model.set_OtherSampleId_field(parent_sample.get_OtherSampleId_field())
            child_sample_model.set_ExemplarSampleType_field(parent_sample.get_ExemplarSampleType_field())
            # child_sample_model.set_RowPosition_field(parent_sample.get_RowPosition_field)
            # child_sample_model.set_ColPosition_field(parent_sample.get_ColPosition_field)
            parent_sample.add_child(child_sample_model)
            experiment_model.add_child(child_sample_model)

    def get_specimen_models(self, eln_records: list[ELNSampleDetailModel]):
        specimens: list[SampleModel] = []
        all_samples: list[SampleModel] = self.exp_handler.get_step_models("Specimens", SampleModel)
        for eln_record in eln_records:
            ...  # remainder of this method was not visible in the screenshots
        return specimens

    def add_control_samples(self, controls: list[ELNExperimentDetailModel], scan_rack_prep_details: list[ELNSampleDetailModel],
                            patient_sample_count: int, entry_name: str):
        plate = TBLR96WellPlateHelper()
        sample_models: list[SampleModel] = []
        consumable_lots: list[str] = [control.get_ConsumableLot_field() for control in controls]
        record_consumable_items: list[ConsumableItemModel] = self.rec_handler.query_models(ConsumableItemModel,
                                                                                           ConsumableItemModel.LOTNUMBER__FIELD_NAME.field_name,
                                                                                           list(consumable_lots))
        self.rel_man.load_parents_of_type(record_consumable_items, SampleModel)
        control_count: int = 0
        for inv_item in record_consumable_items:
            sample: SampleModel = inv_item.get_parent_of_type(SampleModel)
            if sample is not None:
                sample_models.append(sample)
            control_detail: ELNExperimentDetailModel = self.get_control_details(controls, inv_item)
            if control_detail is not None and sample is not None:
                tube_barcode = control_detail.get_field_value("ControlTubeBarCode")
                if tube_barcode is None:
                    tube_barcode = control_detail.get_field_value("TubeBarcode2")
                sample.set_TubeBarcode_field(tube_barcode)
                detail: ELNSampleDetailModel = self.get_related_details(sample.get_OtherSampleId_field(), scan_rack_prep_details)
                if detail is None:
                    detail = self.exp_handler.add_eln_row(entry_name, ELNSampleDetailModel)
                if entry_name == EXTRACTION_DNA_ISOLATES_ENTRY:
                    batch_order = patient_sample_count + control_count + 1
                    well_pos = plate.get_row_col_for_batch_number(batch_order)
                    wellid = str(well_pos[0]) + str(well_pos[1])
                    sample.set_RowPosition_field(well_pos[0])
                    sample.set_ColPosition_field(well_pos[1])
                    detail.set_BatchOrder_field(batch_order)
                    detail.set_OtherSampleId_field(sample.get_OtherSampleId_field())
                    detail.set_WellID_field(wellid)
                    detail.set_MaterialType_field("Extracted DNA")
                    control_count += 1
                    continue
                detail.set_BatchOrder_field(patient_sample_count+control_count+1)
                detail.set_OtherSampleId_field(sample.get_OtherSampleId_field())
                detail.set_TubeBarcode_field(tube_barcode)
                detail.set_SpecimenType_field("Control")
                detail.set_Volume_field(sample.get_Volume_field())
                detail.set_VolumeUnits2_field(sample.get_VolumeUnits_field())
            control_count += 1
        return sample_models

    def get_control_details(self, controls: list[ELNExperimentDetailModel], inv_item: ConsumableItemModel):
        for control in controls:
            if control.get_ConsumableLot_field() == inv_item.get_LotNumber_field():
                return control
        return None

    def add_patient_samples(self, sample_details: list[ELNSampleDetailModel], scan_rack_prep_details: list[ELNSampleDetailModel],
                            entry_name: str):
        entry_options: dict[str, str] = self.exp_handler.get_step_options(EXTRACTION_DNA_ISOLATES_ENTRY)
        for sample_detail in sample_details:
            detail: ELNSampleDetailModel = self.get_related_details(sample_detail.get_OtherSampleId_field(), scan_rack_prep_details)
            if detail is None:
                detail = self.exp_handler.add_eln_row(entry_name, ELNSampleDetailModel)
            if entry_name == EXTRACTION_DNA_ISOLATES_ENTRY:
                detail.set_BatchOrder_field(sample_detail.get_BatchOrder_field())
                detail.set_NeoLINKAccession_field(sample_detail.get_NeoLINKAccession_field())
                detail.set_Tests_field(sample_detail.get_TestSet_field())
                detail.set_TestNames_field(sample_detail.get_TestNames_field())
                detail.set_TestAbbr_field(sample_detail.get_TestAbbr_field())
                detail.set_PatientName_field(sample_detail.get_PatientName_field())
                detail.set_OtherSampleId_field(sample_detail.get_OtherSampleId_field())
                detail.set_WellID_field(sample_detail.get_WellID_field())
                detail.set_MaterialType_field("Extracted DNA")
                detail.set_PbTubeNo_field(sample_detail.get_PbTubeNo_field())
                detail.set_C_MovementInitials_field(sample_detail.get_C_MovementInitials_field())
                detail.set_C_Reason_field(sample_detail.get_C_Reason_field())
                detail.set_ClientSPID_field(sample_detail.get_ClientSPID_field())
                detail.set_ElutionVolume_field(entry_options.get("DEFAULT VOL"))
                detail.set_VolumeUnits2_field(entry_options.get("DEFAULT VOL UNIT"))
                detail.set_C_DueDate_field(sample_detail.get_C_DueDate_field())
                detail.set_PatientName_field(sample_detail.get_PatientName_field())
                detail.set_ProjectID_field(sample_detail.get_ProjectID_field())
                detail.set_ProjectPriority_field(sample_detail.get_ProjectPriority_field())
                continue
            detail.set_BatchOrder_field(sample_detail.get_BatchOrder_field())
            detail.set_NeoLINKAccession_field(sample_detail.get_NeoLINKAccession_field())
            detail.set_Tests_field(sample_detail.get_TestSet_field())
            detail.set_TestNames_field(sample_detail.get_TestNames_field())
            detail.set_OtherSampleId_field(sample_detail.get_OtherSampleId_field())
            detail.set_TubeBarcode_field(sample_detail.get_TubeBarcode_field())
            detail.set_SpecimenType_field(sample_detail.get_SpecimenType_field())
            detail.set_MaterialType_field(sample_detail.get_MaterialType_field())
            detail.set_Volume_field(sample_detail.get_Volume_field())
            detail.set_VolumeUnits2_field(sample_detail.get_VolumeUnits2_field())
            detail.set_PbTubeNo_field(sample_detail.get_PbTubeNo_field())
            #detail.set_WellID_field(sample_detail.get_WellID_field())

    def get_related_details(self, sample_id: str, scan_rack_prep_details: list[ELNSampleDetailModel]):
        for prep_detail in scan_rack_prep_details:
            if prep_detail.get_OtherSampleId_field() == sample_id:
                return prep_detail
        return None


# ---------------------------------------------------------------------------------------------------------------------
# P42-19563: RaDaR Plasma DNA Extraction - Controls entry
# ---------------------------------------------------------------------------------------------------------------------

CPL_POOL_CONTROL = "CPL-Pool (Positive Extraction Control)"
NEC_CONTROL = "NEC (Negative Extraction Control)"
DEFAULT_CONTROL_TYPES = [CPL_POOL_CONTROL, NEC_CONTROL]

# Controls entry option holding the eligible control types, comma separated (AC2: configurable without code changes).
CONTROL_TYPES_OPTION = "CONTROL TYPES"
# Experiment option where the Parent Specimen Quantity (patients + controls) is written on submit (AC13).
PARENT_SPECIMEN_QUANTITY_OPTION = "PARENT SPECIMEN QUANTITY"

SMALL_RUN_MAX_PATIENTS = 22
MAX_PARENT_SPECIMEN_QUANTITY = 48
NEC_EXPIRATION_HOURS = 48

# Controls entry (ELNExperimentDetail) field names.
INVENTORY_ITEM_TYPE_FIELD = "InventoryItemType"
INVENTORY_ITEM_ID_FIELD = "InventoryItemId"
TUBE_BARCODE_FIELD = "ControlTubeBarCode"
TUBE_BARCODE_ALT_FIELD = "TubeBarcode2"
VENDOR_LOT_FIELD = "ConsumableLot"
EXPIRATION_DATE_FIELD = "ExpirationDate"

# Materials Management (ConsumableItem) field names used for generated NEC inventory.
CONSUMABLE_TYPE_FIELD = "ConsumableType"
CONSUMABLE_EXPIRATION_FIELD = "ExpirationDate"


class RadarControlsHelper:
    """Business rules for the RaDaR Plasma DNA Extraction Controls entry (P42-19563)."""

    def __init__(self, handler: NeoWebhookHandler, context: SapioWebhookContext):
        self.handler = handler
        self.context = context
        self.exp_handler = handler.exp_handler

    # ----- configuration -----

    def get_control_types(self) -> list[str]:
        option: str | None = self.exp_handler.get_step_options(CONTROLS_ENTRY).get(CONTROL_TYPES_OPTION)
        if not option:
            return list(DEFAULT_CONTROL_TYPES)
        return [t.strip() for t in option.split(",") if t.strip()]

    @staticmethod
    def is_positive(control_type: str | None) -> bool:
        return control_type is not None and control_type.upper().startswith("CPL")

    @staticmethod
    def is_negative(control_type: str | None) -> bool:
        return control_type is not None and control_type.upper().startswith("NEC")

    def get_type_by_kind(self, positive: bool) -> str:
        check = self.is_positive if positive else self.is_negative
        return next((t for t in self.get_control_types() if check(t)), CPL_POOL_CONTROL if positive else NEC_CONTROL)

    # ----- required minimums (AC3, AC4, AC15, AC16) -----

    @staticmethod
    def required_counts(patient_count: int) -> tuple[int, int]:
        """Returns (required CPL-Pool, required NEC) for the given patient specimen count."""
        if patient_count <= SMALL_RUN_MAX_PATIENTS:
            return 1, 1
        return 1, 2

    def required_controls_message(self, patient_count: int) -> str:
        cpl, nec = self.required_counts(patient_count)
        return (f"An experiment with {patient_count} patient specimen(s) requires a minimum of "
                f"{cpl} {self.get_type_by_kind(True)} and {nec} {self.get_type_by_kind(False)}. "
                f"Required controls cannot be removed.")

    def meets_minimum(self, controls: list[ELNExperimentDetailModel], patient_count: int) -> bool:
        cpl, nec = self.required_counts(patient_count)
        types = [c.get_field_value(INVENTORY_ITEM_TYPE_FIELD) for c in controls]
        return (sum(1 for t in types if self.is_positive(t)) >= cpl
                and sum(1 for t in types if self.is_negative(t)) >= nec)

    # ----- quantities (AC12, AC13) -----

    @staticmethod
    def parent_specimen_quantity(patient_count: int, control_count: int) -> int:
        return patient_count + control_count

    def get_patient_count(self) -> int:
        return len(self.exp_handler.get_step_models(PARENT_SPECIMENS_ENTRY, ELNSampleDetailModel))

    def get_controls(self) -> list[ELNExperimentDetailModel]:
        return self.exp_handler.get_step_models(CONTROLS_ENTRY, ELNExperimentDetailModel)

    # ----- initialization (AC3, AC4) -----

    def initialize_default_controls(self, patient_count: int) -> None:
        """Creates the default control rows when the Controls entry has none yet."""
        if len(self.get_controls()) > 0:
            return
        cpl, nec = self.required_counts(patient_count)
        row_types = [self.get_type_by_kind(True)] * cpl + [self.get_type_by_kind(False)] * nec
        for control_type in row_types:
            row: ELNExperimentDetailModel = self.exp_handler.add_eln_row(CONTROLS_ENTRY, ELNExperimentDetailModel)
            row.set_field_value(INVENTORY_ITEM_TYPE_FIELD, control_type)
        self.handler.rec_man.store_and_commit()

    # ----- validation (AC8, AC12, AC15, AC16, AC17) -----

    @staticmethod
    def get_tube_barcode(control: ELNExperimentDetailModel) -> str | None:
        tube_barcode = control.get_field_value(TUBE_BARCODE_FIELD)
        if not tube_barcode:
            tube_barcode = control.get_field_value(TUBE_BARCODE_ALT_FIELD)
        return tube_barcode or None

    def validate(self, controls: list[ELNExperimentDetailModel], patient_count: int) -> str | None:
        """Returns a user facing error message when the Controls entry cannot be submitted, otherwise None."""
        errors: list[str] = []
        types = self.get_control_types()
        for index, control in enumerate(controls, start=1):
            control_type = control.get_field_value(INVENTORY_ITEM_TYPE_FIELD)
            if control_type not in types:
                errors.append(f"Row {index}: '{control_type}' is not an eligible control type ({', '.join(types)}).")
            elif self.get_tube_barcode(control) is None:
                errors.append(f"Row {index}: TUBE BARCODE is required for {control_type}.")
        if not self.meets_minimum(controls, patient_count):
            errors.append(self.required_controls_message(patient_count))
        quantity = self.parent_specimen_quantity(patient_count, len(controls))
        if quantity > MAX_PARENT_SPECIMEN_QUANTITY:
            errors.append(f"Parent Specimen Quantity is {quantity} ({patient_count} patient specimens + "
                          f"{len(controls)} controls), maximum is {MAX_PARENT_SPECIMEN_QUANTITY}. "
                          f"Remove {quantity - MAX_PARENT_SPECIMEN_QUANTITY} excess control(s) before submitting.")
        return "\n".join(errors) if errors else None

    # ----- submit (AC7, AC9, AC10, AC13, AC18) -----

    def finalize_controls(self, controls: list[ELNExperimentDetailModel], patient_count: int) -> str | None:
        """
        Validates the Controls entry and populates the system generated values on submit. Returns an error message
        when the entry cannot be submitted.
        """
        error = self.validate(controls, patient_count)
        if error is not None:
            return error
        error = self.assign_positive_control_inventory([c for c in controls
                                                         if self.is_positive(c.get_field_value(INVENTORY_ITEM_TYPE_FIELD))])
        if error is not None:
            return error
        self.create_negative_control_inventory([c for c in controls
                                                 if self.is_negative(c.get_field_value(INVENTORY_ITEM_TYPE_FIELD))])
        self.exp_handler.add_experiment_options({
            PARENT_SPECIMEN_QUANTITY_OPTION: str(self.parent_specimen_quantity(patient_count, len(controls)))
        })
        self.handler.rec_man.store_and_commit()
        return None

    def assign_positive_control_inventory(self, positives: list[ELNExperimentDetailModel]) -> str | None:
        """AC7: the CPL-Pool INVENTORY ITEM ID is the inventory item that matches its TUBE BARCODE."""
        if len(positives) == 0:
            return None
        barcodes = [self.get_tube_barcode(c) for c in positives]
        samples: list[SampleModel] = self.handler.rec_handler.query_models(SampleModel, "TubeBarcode", barcodes)
        self.handler.rel_man.load_children_of_type(samples, ConsumableItemModel)
        samples_by_barcode: dict[str, SampleModel] = {s.get_TubeBarcode_field(): s for s in samples}
        missing: list[str] = []
        for control in positives:
            barcode = self.get_tube_barcode(control)
            sample = samples_by_barcode.get(barcode)
            if sample is None:
                missing.append(barcode)
                continue
            control.set_field_value(INVENTORY_ITEM_ID_FIELD, sample.get_SampleId_field())
            consumable: ConsumableItemModel | None = sample.get_child_of_type(ConsumableItemModel)
            if consumable is not None:
                if not control.get_field_value(VENDOR_LOT_FIELD):
                    control.set_field_value(VENDOR_LOT_FIELD, consumable.get_LotNumber_field())
                if not control.get_field_value(EXPIRATION_DATE_FIELD):
                    control.set_field_value(EXPIRATION_DATE_FIELD,
                                            consumable.get_field_value(CONSUMABLE_EXPIRATION_FIELD))
        if missing:
            return f"No {self.get_type_by_kind(True)} inventory item found for TUBE BARCODE(s): {', '.join(missing)}."
        return None

    def create_negative_control_inventory(self, negatives: list[ELNExperimentDetailModel]) -> None:
        """
        AC7, AC9, AC10, AC18: each NEC gets the next system-wide inventory item ID, SPECIMEN TYPE = Control,
        VENDOR LOT NUMBER = [Experiment Name]_NEC_XX, EXPIRATION DATE = experiment creation + 48 hours, and a
        matching Materials Management inventory record.
        """
        new_negatives = [c for c in negatives if not c.get_field_value(INVENTORY_ITEM_ID_FIELD)]
        if len(new_negatives) == 0:
            return
        experiment = self.context.eln_experiment
        expiration = experiment.date_created + int(timedelta(hours=NEC_EXPIRATION_HOURS).total_seconds() * 1000)
        used_lots = {c.get_field_value(VENDOR_LOT_FIELD) for c in negatives}
        sample_ids: list[str] = self.handler.fnd_acc_man.get_accession_with_config_list(
            SampleModel.DATA_TYPE_NAME, "SampleId", len(new_negatives))
        nec_type = self.get_type_by_kind(False)
        sequence = 0
        for control, sample_id in zip(new_negatives, sample_ids):
            sequence += 1
            vendor_lot = f"{experiment.notebook_experiment_name}_NEC_{sequence:02d}"
            while vendor_lot in used_lots:
                sequence += 1
                vendor_lot = f"{experiment.notebook_experiment_name}_NEC_{sequence:02d}"
            used_lots.add(vendor_lot)
            tube_barcode = self.get_tube_barcode(control)

            sample: SampleModel = self.handler.inst_man.add_new_record_of_type(SampleModel)
            sample.set_SampleId_field(sample_id)
            sample.set_OtherSampleId_field(sample_id)
            sample.set_TubeBarcode_field(tube_barcode)
            sample.set_ExemplarSampleType_field("Control")

            consumable: ConsumableItemModel = self.handler.inst_man.add_new_record_of_type(ConsumableItemModel)
            consumable.set_LotNumber_field(vendor_lot)
            consumable.set_field_value(CONSUMABLE_TYPE_FIELD, nec_type)
            consumable.set_field_value(CONSUMABLE_EXPIRATION_FIELD, expiration)
            sample.add_child(consumable)

            control.set_field_value(INVENTORY_ITEM_ID_FIELD, sample_id)
            control.set_field_value(VENDOR_LOT_FIELD, vendor_lot)
            control.set_field_value(EXPIRATION_DATE_FIELD, expiration)

    # ----- add / remove (AC11, AC12, AC14, AC15, AC16, AC17, AC18) -----

    def locked_message(self) -> str | None:
        if self.exp_handler.step_is_locked(CONTROLS_ENTRY):
            return "The Controls entry is submitted. Select Unlock to Edit before adding or removing controls."
        return None


class InitializeRadarControlsEntry(NeoWebhookHandler):
    """AC3, AC4: creates the default controls. Call from the Parent Specimens submit rule (radar-add-plasma-control)."""

    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        helper = RadarControlsHelper(self, context)
        helper.initialize_default_controls(helper.get_patient_count())
        return SapioWebhookResult(True, refresh_data=True)


class ValidateRadarControlsEntry(NeoWebhookHandler):
    """AC8, AC12, AC15, AC16, AC17: blocks submission of an invalid Controls entry."""

    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        helper = RadarControlsHelper(self, context)
        error = helper.validate(helper.get_controls(), helper.get_patient_count())
        if error is not None:
            return SapioWebhookResult(False, display_text=error)
        return SapioWebhookResult(True)


class AddRadarControl(NeoWebhookHandler):
    """AC11, AC12, AC18: Add Control toolbar button on the Controls entry."""

    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        helper = RadarControlsHelper(self, context)
        locked = helper.locked_message()
        if locked is not None:
            self.callback.display_warning(locked)
            return SapioWebhookResult(True)
        patient_count = helper.get_patient_count()
        controls = helper.get_controls()
        quantity = helper.parent_specimen_quantity(patient_count, len(controls))
        if quantity >= MAX_PARENT_SPECIMEN_QUANTITY:
            self.callback.display_warning(f"Parent Specimen Quantity is already {quantity}. No more controls can be "
                                          f"added (maximum {MAX_PARENT_SPECIMEN_QUANTITY}).")
            return SapioWebhookResult(True)
        selected = self.callback.list_dialog("Select Control Type", helper.get_control_types())
        if not selected:
            return SapioWebhookResult(True)
        row: ELNExperimentDetailModel = self.exp_handler.add_eln_row(CONTROLS_ENTRY, ELNExperimentDetailModel)
        row.set_field_value(INVENTORY_ITEM_TYPE_FIELD, selected[0])
        self.rec_man.store_and_commit()
        return SapioWebhookResult(True, refresh_data=True)


class RemoveRadarControl(NeoWebhookHandler):
    """AC14, AC15, AC16, AC17, AC18: Remove Control toolbar button on the Controls entry."""

    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        helper = RadarControlsHelper(self, context)
        locked = helper.locked_message()
        if locked is not None:
            self.callback.display_warning(locked)
            return SapioWebhookResult(True)
        controls = helper.get_controls()
        if len(controls) == 0:
            return SapioWebhookResult(True)
        labels: dict[str, ELNExperimentDetailModel] = {}
        for index, control in enumerate(controls, start=1):
            barcode = helper.get_tube_barcode(control) or "no barcode"
            labels[f"{index}. {control.get_field_value(INVENTORY_ITEM_TYPE_FIELD)} ({barcode})"] = control
        selected = self.callback.list_dialog("Select Controls to Remove", list(labels.keys()), multi_select=True)
        if not selected:
            return SapioWebhookResult(True)
        to_remove = [labels[label] for label in selected]
        remaining = [c for c in controls if c not in to_remove]
        patient_count = helper.get_patient_count()
        if not helper.meets_minimum(remaining, patient_count):
            self.callback.display_warning(helper.required_controls_message(patient_count))
            return SapioWebhookResult(True)
        self.exp_handler.remove_eln_rows(CONTROLS_ENTRY, to_remove)
        self.rec_man.store_and_commit()
        return SapioWebhookResult(True, refresh_data=True)


class RaDaRAddPlasmaControl(NeoWebhookHandler):
    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        current_step: str = context.active_step.get_name()
        entry_options: dict[str, str] = self.exp_handler.get_step_options(CONTROLS_ENTRY)
        parent_samples: list[ELNSampleDetailModel] = self.exp_handler.get_step_models(PARENT_SPECIMENS_ENTRY, ELNSampleDetailModel)
        patient_sample_count: int = len(parent_samples)
        json_data = self.__parse_JSON()
        default_controls = json_data.get("patientSampleRecords")
        if default_controls is None:
            raise SapioUserErrorException(
                f"Experiment option '{ADD_DEFAULT_PLASMA_CONTROLS_TAG}' is not set or invalid JSON. Please contact system administrator.")
        eln_records: list[ELNExperimentDetailModel] = self.exp_handler.get_step_models(CONTROLS_ENTRY,
                                                                                        ELNExperimentDetailModel)

        def_control_types: list[str] = []
        if entry_options.keys().__contains__(AUTO_INV_ITEM_CREATION_CONTROL_TYPE_TAG):
            if entry_options[AUTO_INV_ITEM_CREATION_CONTROL_TYPE_TAG].__contains__("|"):
                def_control_types = entry_options[AUTO_INV_ITEM_CREATION_CONTROL_TYPE_TAG].split("|")
            else:
                def_control_types.append(entry_options[AUTO_INV_ITEM_CREATION_CONTROL_TYPE_TAG])
        records_inventory_parts: list[ConsumableModel] = self.rec_handler.query_models(ConsumableModel,
                                                                                         ConsumableModel.CONSUMABLETYPE__FIELD_NAME.field_name,
                                                                                         def_control_types)

        exp_name: str = context.eln_experiment.notebook_experiment_name
        if current_step == VISIBLE_PARENT_SPECIMEN_ENTRY:
            if len(eln_records) > 0:
                self.exp_handler.remove_eln_rows(CONTROLS_ENTRY, eln_records)
            self.add_automate_controls(default_controls, exp_name, records_inventory_parts, patient_sample_count)

        if current_step != VISIBLE_PARENT_SPECIMEN_ENTRY:
            values_to_add: list[str] = []
            total_parent_sample_count: int = len(parent_samples) + len(eln_records)
            addControlRestriction = json_data.get("addControlRestriction")
            sampleCountCondition = addControlRestriction.get("sampleCountCondition")
            if sampleCountCondition.__contains__("[patientSamplesCount]"):
                sampleCountCondition = sampleCountCondition.replace("[patientSamplesCount]", str(total_parent_sample_count))
            result_cond = eval(sampleCountCondition)
            if not result_cond:
                raise SapioUserErrorException("Unable to add additional control as maximum batch size exceeded.")

            success, tag_value = check_requirements(context, ADD_REMOVE_CONTROL_TAG)
            if not success:
                return SapioWebhookResult(False, display_text=tag_value)
            if len(tag_value) > 0:
                options: list[str] = [opt.strip() for opt in tag_value.split("|") if opt.strip()]
                if len(options) == 1:
                    # Single option, no dialog needed
                    values_to_add = options
                else:
                    # Multiple options, show dialog
                    values_to_add = self.callback.list_dialog("Please select a control type",
                                                              options, multi_select=False)
            elif tag_value is None or tag_value.strip() == "":
                # Add another record based on selection from default rows, ie: no alternate selections
                selected_records: list[ELNExperimentDetailModel] = self.inst_man.add_existing_records_of_type(
                    context.data_record_list, ELNExperimentDetailModel)
                if len(selected_records) <= 0:
                    return SapioWebhookResult(False, display_text="No existing control records selected to add.")
                for record in selected_records:
                    values_to_add.append(record.get_ConsumableType_field())

            if len(values_to_add) <= 0:
                return SapioWebhookResult(False, display_text="No control types selected to add.")
            for control_type in values_to_add:
                if control_type in def_control_types:
                    self.add_manual_default_control(exp_name, control_type, context)
                else:
                    selection_order: str = f"{zero_pad(str(len(eln_records) + 1), 2)}"
                    new_control_record = self.exp_handler.add_eln_row(context.active_step.get_name())
                    new_control_record.set_field_value(
                        ELNExperimentDetailModel.CONSUMABLETYPE__FIELD_NAME.field_name, control_type)
                    new_control_record.set_field_value(
                        ELNExperimentDetailModel.SELECTIONORDER__FIELD_NAME.field_name, selection_order)

        self.rec_man.store_and_commit()
        return SapioWebhookResult(True)

    def add_manual_default_control(self, exp_name: str, def_control_type: str, context: SapioWebhookContext):
        eln_records: list[ELNExperimentDetailModel] = self.exp_handler.get_step_models(CONTROLS_ENTRY,
                                                                                        ELNExperimentDetailModel)
        new_controls = self.exp_handler.add_eln_rows(CONTROLS_ENTRY, 1)
        criteria = AccessionSystemCriteriaPojo(f"{exp_name}")
        acc_man = DataMgmtServer.get_accession_manager(self.user)
        new_vals: list[str] = acc_man.accession_for_system(1, criteria)

        ret_vals: list[str] = []
        for val in new_vals:
            ret_vals.append(f"{zero_pad(val, 2)}")
        records_inventory_parts: list[ConsumableModel] = self.rec_handler.query_models(ConsumableModel,
                                                                                         ConsumableModel.CONSUMABLETYPE__FIELD_NAME.field_name,
                                                                                         def_control_type)
        record_inv_part_model: ConsumableModel = records_inventory_parts.pop()
        #[ExpName]_NTC_XX
        for control in new_controls:
            control.set_field_value(ELNExperimentDetailModel.CONSUMABLETYPE__FIELD_NAME.field_name, def_control_type)
            val = ret_vals.pop()
            vendor_lot_no = exp_name + "_NEC_" + val
            selection_order: str = f"{zero_pad(str(len(eln_records)+1), 2)}"
            control.set_field_value(ELNExperimentDetailModel.C_VENDORLOTNUMBER__FIELD_NAME.field_name, vendor_lot_no)
            control.set_field_value(ELNExperimentDetailModel.SELECTIONORDER__FIELD_NAME.field_name, selection_order)
            inventory_item: ConsumableItemModel = self.create_inventory_records(record_inv_part_model, vendor_lot_no, selection_order)
            if inventory_item is not None:
                control.set_field_value("C_ExpirationDate", inventory_item.get_field_value('ExpirationDate'))

    def add_automate_controls(self, default_controls: Any, exp_name: str, records_inventory_parts: list[ConsumableModel],
                              patient_sample_count: int):
        for option in default_controls:
            sampleCountCondition: str = option['sampleCountCondition']
            if sampleCountCondition.__contains__("[patientSamplesCount]"):
                sampleCountCondition = sampleCountCondition.replace("[patientSamplesCount]", str(patient_sample_count))
            result_cond = eval(sampleCountCondition)
            if result_cond:
                controls = option['controls']
                for control in controls:
                    controlType = control['controlType']
                    orderNo = control['orderNo']
                    autoVendorLotNoCreation = control['autoVendorLotNoCreation']
                    vendorLotNoFormat = control['vendorLotNoFormat']
                    if autoVendorLotNoCreation == "true":
                        self.add_default_control(exp_name, controlType, records_inventory_parts, vendorLotNoFormat, orderNo)
                    else:
                        new_controls = self.exp_handler.add_eln_rows(CONTROLS_ENTRY, 1)
                        for new_control in new_controls:
                            new_control.set_field_value(ELNExperimentDetailModel.CONSUMABLETYPE__FIELD_NAME.field_name, controlType)
                            selection_order: str = f"{zero_pad(orderNo, 2)}"
                            new_control.set_field_value(ELNExperimentDetailModel.SELECTIONORDER__FIELD_NAME.field_name,
                                                        selection_order)

    def __parse_JSON(self):
        optionsJSON: str = ''
        # Get JSON from Experiment Options
        try:
            optionsValue = self.exp_handler.get_step_options(CONTROLS_ENTRY).get(ADD_DEFAULT_PLASMA_CONTROLS_TAG)
            if optionsValue:
                optionsJSON = json.loads(optionsValue)
        except:
            raise SapioUserErrorException(
                f"Experiment option '{ADD_DEFAULT_PLASMA_CONTROLS_TAG}' is not set or invalid JSON. Please contact system administrator.")
        return optionsJSON

    def add_default_control(self, exp_name: str, def_control_type: str, records_inventory_parts: list[ConsumableModel],
                            vendor_lot_no_format: str, order: str):
        new_controls = self.exp_handler.add_eln_rows(CONTROLS_ENTRY, 1)
        criteria = AccessionSystemCriteriaPojo(f"{exp_name}")
        acc_man = DataMgmtServer.get_accession_manager(self.user)
        new_vals: list[str] = acc_man.accession_for_system(1, criteria)

        ret_vals: list[str] = []
        for val in new_vals:
            ret_vals.append(f"{zero_pad(val, 2)}")
        record_inv_part_model: ConsumableModel = self.retrieve_inv_model(records_inventory_parts, def_control_type)
        #[ExpName]_NTC_XX
        for control in new_controls:
            control.set_field_value(ELNExperimentDetailModel.CONSUMABLETYPE__FIELD_NAME.field_name, def_control_type)
            val = ret_vals.pop()
            if vendor_lot_no_format.__contains__("[ExperimentName]"):
                vendor_lot_no_format = vendor_lot_no_format.replace("[ExperimentName]", exp_name)
            if vendor_lot_no_format.__contains__("XX"):
                vendor_lot_no_format = vendor_lot_no_format.replace("XX", val)
            selection_order: str = f"{zero_pad(order, 2)}"
            control.set_field_value(ELNExperimentDetailModel.C_VENDORLOTNUMBER__FIELD_NAME.field_name, vendor_lot_no_format)
            control.set_field_value(ELNExperimentDetailModel.SELECTIONORDER__FIELD_NAME.field_name, selection_order)
            inventory_item = self.create_inventory_records(record_inv_part_model, vendor_lot_no_format, selection_order)
            if inventory_item is not None:
                control.set_field_value("C_ExpirationDate", inventory_item.get_field_value('ExpirationDate'))

    def create_inventory_records(self, inv_type_model: ConsumableModel, vendor_lot_number: str, selection_order: str):
        # Create ConsumableItem
        new_consumable_item: ConsumableItemModel = self.inst_man.add_new_record_of_type(ConsumableItemModel)
        new_consumable_item.set_C_VendorLotNumber_field(vendor_lot_number)
        new_consumable_item.set_ConsumableName_field(inv_type_model.get_ConsumableName_field())
        new_consumable_item.set_ConsumableType_field(inv_type_model.get_ConsumableType_field())

        # Create Sample Model based on each reagent lot id
        new_sample: SampleModel = self.inst_man.add_new_record_of_type(SampleModel)
        #new_sample.set_C_MaterialType_field("Scraping Tube")
        new_sample.set_ExemplarSampleType_field("Control")
        new_sample.set_C_SelectionOrder_field(int(selection_order))
        new_sample.add_child(new_consumable_item)
        new_sample.add_parent(inv_type_model)
        # Store and commit to get newly created Inventory samples
        self.rec_man.store_and_commit()
        record_consumable_items: list[ConsumableItemModel] = (
            self.rec_handler.query_models(ConsumableItemModel,
                                          ConsumableItemModel.C_VENDORLOTNUMBER__FIELD_NAME.field_name,
                                          list(vendor_lot_number)))
        inventory_item: ConsumableItemModel = record_consumable_items.pop() if len(
            record_consumable_items) > 0 else None
        return inventory_item

    def retrieve_inv_model(self, inv_type_models: list[ConsumableModel], inventory_type: str):
        for inv_type_model in inv_type_models:
            inv_type = inv_type_model.get_ConsumableType_field()
            if inv_type == inventory_type:
                return inv_type_model
        return None
