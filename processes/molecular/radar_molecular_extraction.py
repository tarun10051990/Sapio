# NOTE: Partial transcription of neogenomics-webhooks/processes/molecular/radar_molecular_extraction.py
# taken from screenshots (lines ~433-593 of the original file). Imports, constants, data type models and the
# other handlers in this module (lines 1-432 and 594+) were not visible and are not reproduced here.


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
