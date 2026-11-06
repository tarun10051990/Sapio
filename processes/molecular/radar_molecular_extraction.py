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

SMALL_RUN_MAX_PATIENTS = 22
MAX_PARENT_SPECIMEN_QUANTITY = 48
NEC_EXPIRATION_HOURS = 48
# Experiment option where the Parent Specimen Quantity (patients + controls) is written on submit (AC13).
PARENT_SPECIMEN_QUANTITY_OPTION = "PARENT SPECIMEN QUANTITY"

# Controls entry (ELNExperimentDetail) fields.
CONTROL_TYPE_FIELD = "ConsumableType"         # INVENTORY ITEM TYPE
INVENTORY_ITEM_ID_FIELD = "ConsumableLot"     # INVENTORY ITEM ID (matched to ConsumableItem.LotNumber downstream)
TUBE_BARCODE_FIELD = "ControlTubeBarCode"
TUBE_BARCODE_ALT_FIELD = "TubeBarcode2"


class RadarControlsHelper:
    """Submit-time business rules for the RaDaR Plasma DNA Extraction Controls entry (P42-19563)."""

    def __init__(self, handler: NeoWebhookHandler, context: SapioWebhookContext):
        self.handler = handler
        self.context = context
        self.exp_handler = handler.exp_handler

    @staticmethod
    def is_positive(control_type: str | None) -> bool:
        return control_type is not None and control_type.upper().startswith("CPL")

    @staticmethod
    def is_negative(control_type: str | None) -> bool:
        return control_type is not None and control_type.upper().startswith("NEC")

    @staticmethod
    def required_counts(patient_count: int) -> tuple[int, int]:
        """AC15, AC16: returns (required CPL-Pool, required NEC) for the given patient specimen count."""
        if patient_count <= SMALL_RUN_MAX_PATIENTS:
            return 1, 1
        return 1, 2

    def required_controls_message(self, patient_count: int) -> str:
        cpl, nec = self.required_counts(patient_count)
        return (f"An experiment with {patient_count} patient specimen(s) requires a minimum of {cpl} "
                f"CPL-Pool (Positive Extraction Control) and {nec} NEC (Negative Extraction Control). "
                f"Required controls cannot be removed.")

    def meets_minimum(self, controls: list[ELNExperimentDetailModel], patient_count: int) -> bool:
        cpl, nec = self.required_counts(patient_count)
        types = [c.get_field_value(CONTROL_TYPE_FIELD) for c in controls]
        return (sum(1 for t in types if self.is_positive(t)) >= cpl
                and sum(1 for t in types if self.is_negative(t)) >= nec)

    def get_patient_count(self) -> int:
        return len(self.exp_handler.get_step_models(PARENT_SPECIMENS_ENTRY, ELNSampleDetailModel))

    def get_controls(self) -> list[ELNExperimentDetailModel]:
        return self.exp_handler.get_step_models(CONTROLS_ENTRY, ELNExperimentDetailModel)

    @staticmethod
    def get_tube_barcode(control: ELNExperimentDetailModel) -> str | None:
        tube_barcode = control.get_field_value(TUBE_BARCODE_FIELD)
        if not tube_barcode:
            tube_barcode = control.get_field_value(TUBE_BARCODE_ALT_FIELD)
        return tube_barcode or None

    def validate(self, controls: list[ELNExperimentDetailModel], patient_count: int) -> str | None:
        """AC8, AC12, AC15, AC16, AC17: returns a user facing error when the entry cannot be submitted."""
        errors: list[str] = []
        for index, control in enumerate(controls, start=1):
            if self.get_tube_barcode(control) is None:
                errors.append(f"Row {index}: TUBE BARCODE is required for {control.get_field_value(CONTROL_TYPE_FIELD)}.")
        if not self.meets_minimum(controls, patient_count):
            errors.append(self.required_controls_message(patient_count))
        quantity = patient_count + len(controls)
        if quantity > MAX_PARENT_SPECIMEN_QUANTITY:
            errors.append(f"Parent Specimen Quantity is {quantity} ({patient_count} patient specimens + "
                          f"{len(controls)} controls), maximum is {MAX_PARENT_SPECIMEN_QUANTITY}. "
                          f"Remove {quantity - MAX_PARENT_SPECIMEN_QUANTITY} excess control(s) before submitting.")
        return "\n".join(errors) if errors else None

    def finalize_controls(self, controls: list[ELNExperimentDetailModel], patient_count: int) -> str | None:
        """AC7, AC13, AC18: validates, assigns CPL-Pool inventory item IDs and updates Parent Specimen Quantity."""
        error = self.validate(controls, patient_count)
        if error is not None:
            return error
        error = self.assign_positive_control_inventory(
            [c for c in controls if self.is_positive(c.get_field_value(CONTROL_TYPE_FIELD))])
        if error is not None:
            return error
        self.exp_handler.add_experiment_options({PARENT_SPECIMEN_QUANTITY_OPTION: str(patient_count + len(controls))})
        self.handler.rec_man.store_and_commit()
        return None

    def assign_positive_control_inventory(self, positives: list[ELNExperimentDetailModel]) -> str | None:
        """AC7: the CPL-Pool INVENTORY ITEM ID is the inventory item whose sample has the scanned TUBE BARCODE."""
        positives = [c for c in positives if not c.get_field_value(INVENTORY_ITEM_ID_FIELD)]
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
            consumable: ConsumableItemModel | None = sample.get_child_of_type(ConsumableItemModel) if sample else None
            if consumable is None:
                missing.append(barcode)
                continue
            control.set_field_value(INVENTORY_ITEM_ID_FIELD, consumable.get_LotNumber_field())
            control.set_field_value(ELNExperimentDetailModel.C_VENDORLOTNUMBER__FIELD_NAME.field_name,
                                    consumable.get_C_VendorLotNumber_field())
            control.set_field_value("C_ExpirationDate", consumable.get_field_value("ExpirationDate"))
        if missing:
            return f"No CPL-Pool (Positive Extraction Control) inventory item found for TUBE BARCODE(s): {', '.join(missing)}."
        return None


class ValidateRadarControlsEntry(NeoWebhookHandler):
    """AC8, AC12, AC15, AC16, AC17: blocks submission of an invalid Controls entry."""

    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        helper = RadarControlsHelper(self, context)
        error = helper.validate(helper.get_controls(), helper.get_patient_count())
        if error is not None:
            return SapioWebhookResult(False, display_text=error)
        return SapioWebhookResult(True)


class RemoveRadarControl(NeoWebhookHandler):
    """AC14, AC15, AC16, AC17, AC18: Remove Control toolbar button on the Controls entry."""

    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        if self.exp_handler.step_is_locked(CONTROLS_ENTRY):
            return SapioWebhookResult(False, display_text="The Controls entry is submitted. "
                                                          "Select Unlock to Edit before removing controls.")
        helper = RadarControlsHelper(self, context)
        controls = helper.get_controls()
        to_remove: list[ELNExperimentDetailModel] = self.inst_man.add_existing_records_of_type(
            context.data_record_list, ELNExperimentDetailModel)
        if len(to_remove) == 0:
            return SapioWebhookResult(False, display_text="No control rows selected to remove.")
        remove_ids = {r.record_id for r in to_remove}
        remaining = [c for c in controls if c.record_id not in remove_ids]
        patient_count = helper.get_patient_count()
        if not helper.meets_minimum(remaining, patient_count):
            return SapioWebhookResult(False, display_text=helper.required_controls_message(patient_count))
        self.exp_handler.remove_eln_rows(CONTROLS_ENTRY, to_remove)
        self.rec_man.store_and_commit()
        return SapioWebhookResult(True, refresh_data=True)


class RaDaRAddPlasmaControl(NeoWebhookHandler):
    def execute(self, context: SapioWebhookContext) -> SapioWebhookResult:
        current_step: str = context.active_step.get_name()
        self.__selection_order = None
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
            if self.exp_handler.step_is_locked(CONTROLS_ENTRY):
                return SapioWebhookResult(False, display_text="The Controls entry is submitted. "
                                                              "Select Unlock to Edit before adding controls.")
            values_to_add: list[str] = []
            total_parent_sample_count: int = len(parent_samples) + len(eln_records)
            addControlRestriction = json_data.get("addControlRestriction")
            if not self.__within_add_restriction(addControlRestriction, total_parent_sample_count):
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
            if not self.__within_add_restriction(addControlRestriction, total_parent_sample_count + len(values_to_add) - 1):
                raise SapioUserErrorException("Unable to add additional control as maximum batch size exceeded.")
            for control_type in values_to_add:
                if control_type in def_control_types:
                    self.add_manual_default_control(exp_name, control_type, context)
                else:
                    selection_order: str = self.__next_selection_order()
                    new_control_record = self.exp_handler.add_eln_row(context.active_step.get_name())
                    new_control_record.set_field_value(
                        ELNExperimentDetailModel.CONSUMABLETYPE__FIELD_NAME.field_name, control_type)
                    new_control_record.set_field_value(
                        ELNExperimentDetailModel.SELECTIONORDER__FIELD_NAME.field_name, selection_order)

        self.rec_man.store_and_commit()
        return SapioWebhookResult(True)

    def add_manual_default_control(self, exp_name: str, def_control_type: str, context: SapioWebhookContext):
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
        if len(records_inventory_parts) == 0:
            raise SapioUserErrorException(f"No inventory part of type '{def_control_type}' is configured. "
                                          f"Please contact system administrator.")
        record_inv_part_model: ConsumableModel = records_inventory_parts[0]
        #[ExpName]_NTC_XX
        for control in new_controls:
            control.set_field_value(ELNExperimentDetailModel.CONSUMABLETYPE__FIELD_NAME.field_name, def_control_type)
            val = ret_vals.pop()
            vendor_lot_no = exp_name + "_NEC_" + val
            selection_order: str = self.__next_selection_order()
            control.set_field_value(ELNExperimentDetailModel.C_VENDORLOTNUMBER__FIELD_NAME.field_name, vendor_lot_no)
            control.set_field_value(ELNExperimentDetailModel.SELECTIONORDER__FIELD_NAME.field_name, selection_order)
            inventory_item: ConsumableItemModel = self.create_inventory_records(record_inv_part_model, vendor_lot_no, selection_order)
            self.__apply_inventory_item(control, inventory_item)

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
        if record_inv_part_model is None:
            raise SapioUserErrorException(f"No inventory part of type '{def_control_type}' is configured. "
                                          f"Please contact system administrator.")
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
            self.__apply_inventory_item(control, inventory_item)

    def create_inventory_records(self, inv_type_model: ConsumableModel, vendor_lot_number: str, selection_order: str):
        # Create ConsumableItem
        new_consumable_item: ConsumableItemModel = self.inst_man.add_new_record_of_type(ConsumableItemModel)
        new_consumable_item.set_C_VendorLotNumber_field(vendor_lot_number)
        new_consumable_item.set_ConsumableName_field(inv_type_model.get_ConsumableName_field())
        new_consumable_item.set_ConsumableType_field(inv_type_model.get_ConsumableType_field())
        new_consumable_item.set_field_value("ExpirationDate", self.__nec_expiration_date())

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
                                          [vendor_lot_number]))
        inventory_item: ConsumableItemModel = record_consumable_items.pop() if len(
            record_consumable_items) > 0 else None
        return inventory_item

    def __nec_expiration_date(self) -> int:
        """AC10: 48 hours after the experiment creation date and time."""
        return self.context.eln_experiment.date_created + int(timedelta(hours=NEC_EXPIRATION_HOURS).total_seconds() * 1000)

    @staticmethod
    def __apply_inventory_item(control: ELNExperimentDetailModel, inventory_item: ConsumableItemModel | None):
        """AC7, AC10: copy the generated INVENTORY ITEM ID and EXPIRATION DATE onto the control row."""
        if inventory_item is None:
            return
        control.set_field_value("C_ExpirationDate", inventory_item.get_field_value('ExpirationDate'))
        if inventory_item.get_LotNumber_field():
            control.set_field_value(INVENTORY_ITEM_ID_FIELD, inventory_item.get_LotNumber_field())

    def __next_selection_order(self) -> str:
        if self.__selection_order is None:
            rows = self.exp_handler.get_step_models(CONTROLS_ENTRY, ELNExperimentDetailModel)
            orders = [str(r.get_field_value(ELNExperimentDetailModel.SELECTIONORDER__FIELD_NAME.field_name)) for r in rows]
            self.__selection_order = max([int(o) for o in orders if o.isdigit()], default=0)
        self.__selection_order += 1
        return f"{zero_pad(str(self.__selection_order), 2)}"

    @staticmethod
    def __within_add_restriction(add_control_restriction: dict, total_parent_sample_count: int) -> bool:
        """AC12: evaluates the configured addControlRestriction against the Parent Specimen Quantity."""
        sampleCountCondition: str = add_control_restriction.get("sampleCountCondition")
        if sampleCountCondition.__contains__("[patientSamplesCount]"):
            sampleCountCondition = sampleCountCondition.replace("[patientSamplesCount]", str(total_parent_sample_count))
        return bool(eval(sampleCountCondition))

    def retrieve_inv_model(self, inv_type_models: list[ConsumableModel], inventory_type: str):
        for inv_type_model in inv_type_models:
            inv_type = inv_type_model.get_ConsumableType_field()
            if inv_type == inventory_type:
                return inv_type_model
        return None
